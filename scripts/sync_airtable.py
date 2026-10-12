#!/usr/bin/env python3
"""Pull the Stylezz Airtable base and rewrite the generated parts of index.html.

Runs from a scheduled GitHub Action. It never edits anything outside the
marked sections of index.html and the photo files it downloads. If the data
looks empty or broken it exits with an error and changes nothing.

  AIRTABLE_TOKEN    read-only personal access token (repo secret)
  AIRTABLE_BASE_ID  base id, not secret (defaults to the Stylezz base)

For tests: --fixture file.json reads tables from a file instead of Airtable.
"""
import argparse
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
PHOTO_DIR = ROOT / "assets" / "photos"
DEFAULT_BASE = "app0ZUh1e5odx1fXG"
PHOTO_MAX = (900, 1200)
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
PENDING_LABEL = "Message for price"
MANUAL_SORT_FIELD = "Manual sort"  # Airtable's drag-to-reorder field (text codes like a0, a1, aBG)

# A sync that would leave the site with less than this is treated as broken.
MIN_SERVICES = 5
MIN_PHOTOS = 6
MIN_HOURS = 1

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

warnings = []


class SyncError(Exception):
    pass


def warn(msg):
    warnings.append(msg)
    print("WARNING:", msg)


# ---------- reading Airtable ----------

def api_get(path, token, params=None):
    url = "https://api.airtable.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SyncError("Airtable returned HTTP %s for %s" % (e.code, path.split("?")[0]))


def fetch_table(base, table, token):
    records, offset = [], None
    while True:
        params = {"pageSize": 100, "cellFormat": "json"}
        if offset:
            params["offset"] = offset
        data = api_get("/v0/%s/%s" % (base, urllib.parse.quote(table)), token, params)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return records


def fetch_group_order(base, token):
    data = api_get("/v0/meta/bases/%s/tables" % base, token)
    for t in data.get("tables", []):
        if t.get("name") == "Services":
            for f in t.get("fields", []):
                if f.get("name") == "Group":
                    return [c["name"] for c in f.get("options", {}).get("choices", [])]
    raise SyncError("Could not read the Group choices of the Services table")


def load_data(args):
    if args.fixture:
        d = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        return d["Services"], d["Photos"], d["Hours"], d["Settings"], d["groups"]
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()
    if not token:
        raise SyncError("AIRTABLE_TOKEN is not set")
    base = os.environ.get("AIRTABLE_BASE_ID", DEFAULT_BASE).strip()
    return (
        fetch_table(base, "Services", token),
        fetch_table(base, "Photos", token),
        fetch_table(base, "Hours", token),
        fetch_table(base, "Settings", token),
        fetch_group_order(base, token),
    )


# ---------- turning rows into site data ----------

def text(v):
    return v.strip() if isinstance(v, str) else ""


def sort_key(rec, order_field="Order"):
    f = rec.get("fields", {})
    order = f.get(order_field)
    return (0 if isinstance(order, (int, float)) else 1,
            order if isinstance(order, (int, float)) else 0,
            rec.get("createdTime", ""))


def manual_value(rec):
    v = rec.get("fields", {}).get(MANUAL_SORT_FIELD)
    return v if isinstance(v, str) and v else None


def order_records(records, new_first):
    """Order rows by Airtable's Manual sort field (plain alphabetical comparison of its
    codes). Rows with no code yet go first (newest first) when new_first, else last.
    If nobody has set up manual sort, or the API does not return it, fall back to the
    Order number rules."""
    placed = [r for r in records if manual_value(r)]
    if not placed:
        return photo_order(records) if new_first else sorted(records, key=sort_key)
    placed.sort(key=lambda r: (manual_value(r), r.get("createdTime", "")))
    rest = [r for r in records if not manual_value(r)]
    if new_first:
        rest.sort(key=lambda r: r.get("createdTime", ""), reverse=True)
        return rest + placed
    return placed + sorted(rest, key=sort_key)


def build_services(records, group_order):
    by_group = {}
    for rec in order_records(records, new_first=False):
        f = rec.get("fields", {})
        if not f.get("Show on site"):
            continue
        name, group = text(f.get("Service")), text(f.get("Group"))
        if not name or not group:
            warn("Skipped a service row with no name or group: %r" % (name or group or rec.get("id")))
            continue
        price = text(f.get("Price")) or None
        by_group.setdefault(group, []).append({"name": name, "price": price})
    ordered = [g for g in group_order if g in by_group]
    ordered += [g for g in by_group if g not in ordered]
    return [{"group": g, "items": by_group[g]} for g in ordered]


def build_hours(records):
    rows = []
    for rec in sorted(records, key=sort_key):
        f = rec.get("fields", {})
        days = text(f.get("Days"))
        if not days:
            continue
        rows.append({"days": days, "open": text(f.get("Opens")), "close": text(f.get("Closes"))})
    return rows


def build_settings(records):
    return {text(r.get("fields", {}).get("Setting")): text(r.get("fields", {}).get("Value"))
            for r in records if text(r.get("fields", {}).get("Setting"))}


def photo_path_for(f):
    existing = text(f.get("Existing file"))
    if existing:
        if not re.fullmatch(r"assets/photos/[A-Za-z0-9._-]+\.jpg", existing):
            raise SyncError("Unexpected value in Existing file: %r" % existing)
        return existing
    atts = f.get("Photo") or []
    if atts:
        # The first 20 photos were uploaded under their repo file names (photo-NN.jpg),
        # so a matching file that is already in the repo is reused: no Existing file needed.
        name = atts[0].get("filename", "")
        if re.fullmatch(r"photo-\d\d\.jpg", name) and (PHOTO_DIR / name).exists():
            return "assets/photos/" + name
        if re.fullmatch(r"att[A-Za-z0-9]+", atts[0].get("id", "")):
            return "assets/photos/up-%s.jpg" % atts[0]["id"]
    return None


def download_photo(url, dest):
    if not url.startswith("https://") and not url.startswith("http://localhost"):
        raise SyncError("Refusing to download from %s" % url.split("?")[0])
    with urllib.request.urlopen(url, timeout=90) as resp:
        raw = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise SyncError("Photo is larger than 40 MB")
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail(PHOTO_MAX, Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Saved without EXIF, so camera location data never reaches the public repo.
    img.save(dest, "JPEG", quality=82, optimize=True, progressive=True)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def photo_order(records):
    """New photos (no Order number) come first, newest first. After them come the
    photos that have an Order number, lowest first. So a new upload shows at the top
    with no numbering, and an Order number is only for pinning a photo in place."""
    blank = [r for r in records if not is_number(r.get("fields", {}).get("Order"))]
    blank.sort(key=lambda r: r.get("createdTime", ""), reverse=True)
    numbered = [r for r in records if is_number(r.get("fields", {}).get("Order"))]
    numbered.sort(key=lambda r: (r["fields"]["Order"], r.get("createdTime", "")))
    return blank + numbered


def build_photos(records, download=True):
    photos = []
    for rec in order_records(records, new_first=True):
        f = rec.get("fields", {})
        if not f.get("Show on site"):
            continue
        label = text(f.get("Name")) or text(f.get("Label")) or rec.get("id")
        path = photo_path_for(f)
        if not path:
            warn("Skipped photo %r: no picture attached" % label)
            continue
        dest = ROOT / path
        if not dest.exists():
            atts = f.get("Photo") or []
            if not atts or not atts[0].get("url"):
                warn("Skipped photo %r: file %s is missing and nothing is attached" % (label, path))
                continue
            if not download:
                warn("Would download %s" % path)
            else:
                try:
                    download_photo(atts[0]["url"], dest)
                    print("Downloaded", path)
                except (OSError, SyncError, ValueError) as e:
                    warn("Skipped photo %r: could not download (%s)" % (label, e))
                    continue
        photos.append({"src": path, "tag": text(f.get("Style tag"))})
    return photos


# ---------- hours for Google (structured data) ----------

def parse_days(s):
    names = {d.lower(): d for d in DAYS}
    s = s.strip().lower()
    if s in names:
        return [names[s]]
    m = re.fullmatch(r"([a-z]+)\s+(?:to|-)\s+([a-z]+)", s)
    if m and m.group(1) in names and m.group(2) in names:
        a, b = DAYS.index(names[m.group(1)]), DAYS.index(names[m.group(2)])
        if a <= b:
            return DAYS[a:b + 1]
    return None


def parse_time(s):
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", s.strip().lower())
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2) or 0)
    if not (1 <= h <= 12 and mins < 60):
        return None
    h = h % 12 + (12 if m.group(3) == "pm" else 0)
    return "%02d:%02d" % (h, mins)


def build_hours_spec(hours):
    specs = []
    for row in hours:
        days, opens, closes = parse_days(row["days"]), parse_time(row["open"]), parse_time(row["close"])
        if not days or not opens or not closes:
            if row["open"] or row["close"]:
                warn("Hours row %r left out of Google structured data (could not read it)" % row["days"])
            continue
        specs.append({"@type": "OpeningHoursSpecification",
                      "dayOfWeek": days if len(days) > 1 else days[0],
                      "opens": opens, "closes": closes})
    return specs


# ---------- rewriting index.html ----------

def esc(s):
    return html.escape(s, quote=False)


# "<" is escaped so a value like "</script>" can never break out of the page's script tags.
def jdump(v):
    return json.dumps(v, ensure_ascii=False).replace("<", "\\u003c")


def jcompact(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def replace_once(src, pattern, repl_fn, label):
    found = list(re.finditer(pattern, src, re.S))
    if len(found) != 1:
        raise SyncError("index.html: expected exactly one %s, found %d" % (label, len(found)))
    m = found[0]
    return src[:m.start()] + repl_fn(m) + src[m.end():]


def marked(src, name, body):
    pat = r"(\n[ ]*<!-- airtable:%s:start -->\n)(.*?)(\n[ ]*<!-- airtable:%s:end -->)" % (name, name)
    return replace_once(src, pat, lambda m: m.group(1) + body + m.group(3), "%s markers" % name)


def menu_html(services):
    out = []
    for g in services:
        out.append('      <div class="menu-group">')
        out.append("        <h3>%s</h3>" % esc(g["group"]))
        out.append("        <ul>")
        for it in g["items"]:
            out.append('          <li><span class="item-name">%s</span><span class="item-price">%s</span></li>'
                       % (esc(it["name"]), esc(it["price"] or PENDING_LABEL)))
        out.append("        </ul>")
        out.append("      </div>")
    return "\n".join(out)


def hours_html(hours):
    lines = []
    for h in hours:
        if h["open"] and h["close"]:
            value = "%s to %s" % (h["open"], h["close"])
        else:
            value = "Closed"
        lines.append('      <div class="row"><dt>%s</dt><dd>%s</dd></div>' % (esc(h["days"]), esc(value)))
    return "\n".join(lines)


def services_json(services):
    out = ['  "services": [']
    for gi, g in enumerate(services):
        out.append('    {"group": %s, "items": [' % jdump(g["group"]))
        for ii, it in enumerate(g["items"]):
            comma = "," if ii < len(g["items"]) - 1 else ""
            out.append('      {"name": %s, "price": %s}%s' % (jdump(it["name"]), jdump(it["price"]), comma))
        out.append("    ]}" + ("," if gi < len(services) - 1 else ""))
    out.append("  ],")
    return "\n".join(out)


def hours_json(hours):
    out = ['  "hours": [']
    for i, h in enumerate(hours):
        out.append('    {"days": %s, "open": %s, "close": %s}%s'
                   % (jdump(h["days"]), jdump(h["open"]), jdump(h["close"]), "," if i < len(hours) - 1 else ""))
    out.append("  ],")
    return "\n".join(out)


def photos_json(photos):
    out = ['  "photos": [']
    for i, p in enumerate(photos):
        out.append("    " + jcompact(p) + ("," if i < len(photos) - 1 else ""))
    out.append("  ]")
    return "\n".join(out)


def set_json_string(src, key, value):
    pat = r'(  "%s": )"(?:[^"\\]|\\.)*"' % re.escape(key)
    return replace_once(src, pat, lambda m: m.group(1) + jdump(value), 'SITE key "%s"' % key)


def rewrite_index(src, services, hours, photos, settings):
    src = marked(src, "menu", menu_html(services))
    src = marked(src, "hours", hours_html(hours))

    src = replace_once(src, r'  "services": \[\n.*?\n  \],(?=\n  "pricePendingLabel")',
                       lambda m: services_json(services), "SITE services block")
    src = replace_once(src, r'  "hours": \[\n.*?\n  \],(?=\n  "payment")',
                       lambda m: hours_json(hours), "SITE hours block")
    src = replace_once(src, r'  "photos": \[\n.*?\n  \](?=\n\};)',
                       lambda m: photos_json(photos), "SITE photos block")

    specs = build_hours_spec(hours)
    if specs:
        body = ",\n".join("    " + jdump(s) for s in specs)
        src = replace_once(src, r'(  "openingHoursSpecification": \[\n)(.*?)(\n  \],\n  "sameAs")',
                           lambda m: m.group(1) + body + m.group(3), "JSON-LD opening hours")
    else:
        warn("No readable hours, so Google structured data hours were left as they were")

    price_note = settings.get("Price note")
    if price_note:
        src = set_json_string(src, "priceNote", price_note)
        src = replace_once(src, r'<p class="lede" data-price-note>[^<]*</p>',
                           lambda m: '<p class="lede" data-price-note>%s</p>' % esc(price_note),
                           "price note paragraph")
    booking = settings.get("Booking line")
    if booking:
        src = set_json_string(src, "booking", booking)
        src = replace_once(src, r'(<div class="book-meta">\n      <p>)[^<]*(</p>)',
                           lambda m: m.group(1) + esc(booking) + m.group(2), "booking line")
    payment = settings.get("Payment")
    if payment:
        pay = payment.rstrip(".")
        src = set_json_string(src, "payment", pay)
        src = replace_once(src, r'(<p class="hero-note">)[^<]*?(\. No online booking\.</p>)',
                           lambda m: m.group(1) + esc(pay) + m.group(2), "hero payment note")
        src = replace_once(src, r'(<p><strong>Payment:</strong> )[^<]*?(\.</p>)',
                           lambda m: m.group(1) + esc(pay) + m.group(2), "payment line")
        src = replace_once(src, r'(<p class="fine">)[^<]*?(\. Edmonton, AB\.)',
                           lambda m: m.group(1) + esc(pay) + m.group(2), "footer payment note")
    return src


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="read tables from this JSON file instead of Airtable")
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()

    svc_rec, photo_rec, hours_rec, set_rec, groups = load_data(args)
    services = build_services(svc_rec, groups)
    hours = build_hours(hours_rec)
    settings = build_settings(set_rec)
    photos = build_photos(photo_rec, download=not args.no_download)

    n_services = sum(len(g["items"]) for g in services)
    problems = []
    if n_services < MIN_SERVICES:
        problems.append("only %d services are switched on (need at least %d)" % (n_services, MIN_SERVICES))
    if len(photos) < MIN_PHOTOS:
        problems.append("only %d photos are switched on (need at least %d)" % (len(photos), MIN_PHOTOS))
    if len(hours) < MIN_HOURS:
        problems.append("no opening hours found")
    if problems:
        raise SyncError("Refusing to update the site: " + "; ".join(problems))

    old = INDEX.read_text(encoding="utf-8")
    new = rewrite_index(old, services, hours, photos, settings)
    if new != old:
        INDEX.write_text(new, encoding="utf-8")
        print("index.html updated: %d services, %d photos, %d hours rows" % (n_services, len(photos), len(hours)))
    else:
        print("index.html already up to date")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and warnings:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### Sync warnings\n" + "".join("- %s\n" % w for w in warnings))


if __name__ == "__main__":
    try:
        main()
    except SyncError as e:
        print("ERROR:", e)
        sys.exit(1)
