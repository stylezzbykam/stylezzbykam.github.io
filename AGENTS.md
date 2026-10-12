# Agent guide: Stylezz by Kam site

One-page static site for a braid and natural hair salon in Edmonton, AB. Hosted on GitHub Pages from the `main` branch of this repo (org `stylezzbykam`, repo `stylezzbykam.github.io`, public). No build step. Do not put personal details, keys or tokens in this repo. It is public.

## Layout
- `index.html` - the whole site. Business facts live in two places that must be kept in sync: the visible HTML text (for SEO) and the `SITE` JSON near the bottom (drives the gallery and structured data).
- `pick/index.html` - photo picker the owner used to choose featured photos and tag styles. Output is a text snapshot: `STYLEZZ PICKS v1`, then lines like `1. photo-14 | Stitch braids`.
- `assets/photos/photo-NN.jpg` (900x1200, portrait), `assets/thumbs/` (small versions for the picker), `assets/logo.png`.
- `README.md` - launch checklist. `AGENTS.md` - this file.

## Airtable is now the source of truth for content
Owner edits prices, hours, text and photos in the Airtable base "Stylezz by Kam - Website" (interface "Update the website"). A scheduled GitHub Action (`.github/workflows/sync-airtable.yml`, every 30 min, plus manual "Run workflow") runs `scripts/sync_airtable.py`, which rewrites the generated parts of `index.html` and commits only if something changed.
- Tables: `Services` (Service, Group, Price, Order, Show on site), `Photos` (Name [formula: Photo N - tag, should be the primary field], Photo number [autoNumber], Label [old, unused except in log messages], Photo, Style tag, Order, Show on site, Existing file), `Hours` (Days, Opens, Closes, Order), `Settings` (Price note, Payment, Booking line).
- Generated parts of `index.html`: the `airtable:menu` and `airtable:hours` marker blocks, the `services`, `hours`, `photos`, `payment`, `booking`, `priceNote` entries of `SITE`, the JSON-LD opening hours, the price note paragraph (`data-price-note`), and the payment/booking sentences. Do not hand-edit these; edit Airtable instead. Everything else in `index.html` (hero, hero photo, address, phone, meta tags, styling) is still edited by hand.
- Photo order: photos with no `Order` number come first, newest first; photos with an `Order` number follow, lowest first. A new upload therefore appears at the top with no numbering; `Order` only pins a photo in place. Services/hours with no `Order` go last. Airtable's drag-to-reorder is per view and not available through the API, so the site does not use it.
- New photos are downloaded, resized to fit 900x1200, stripped of EXIF and saved as `assets/photos/up-<attachment id>.jpg`. Old `photo-NN.jpg` rows keep their path in `Existing file`.
- Fail closed: if the data looks empty or broken (fewer than 5 services, 6 photos, no hours), a marker is missing or the token is missing, the script exits non-zero and commits nothing.
- Needs the repo secret `AIRTABLE_TOKEN` (read-only: `data.records:read`, `schema.bases:read`, this base only). Base id `app0ZUh1e5odx1fXG` is not secret. Never paste the token in chat.
- Test offline: `python3 scripts/sync_airtable.py --fixture fixture.json --no-download` (fixture = API-shaped JSON for the four tables plus `groups`). Against unchanged data it must produce no diff.

## Data model
- `SITE.photos` is an array. Each entry is a string path or `{"src": "...", "tag": "Style name"}`. The first 12 are the Featured grid. Tag chips appear automatically when any photo has a tag.
- `SITE.services` holds groups of `{name, price}`. `price: null` renders as "Message for price".
- The hero image and `og:image` should be a photo the owner picked.

## Pushing from a cloud session
Plain `git push` works to session branches once the Claude GitHub App has access to this repo. If a push returns 403 "Claude doesn't have GitHub access", the app lost access; tell the human to re-link it. Fallback that worked before: the Composio GitHub connection (`GITHUB_COMMIT_MULTIPLE_FILES`, inline content, utf-8 or base64) through the Composio remote workbench. Composio is not used at runtime by the site.

## Editing text files (index.html, README, etc.)
1. Edit and test a local copy first (serve with `python3 -m http.server`, check with Playwright, no console errors).
2. In the workbench, fetch the current file from a commit-pinned raw URL: `https://raw.githubusercontent.com/stylezzbykam/stylezzbykam.github.io/<commit-sha>/index.html`. Do not use `/main/`; it can serve a stale copy for minutes after a commit.
3. Apply the same edit as Python string replacements, asserting each target appears exactly once.
4. Compute the git blob SHA (`sha1(b"blob %d\0" % len + bytes)`) and compare it to the local tested copy. Commit only if equal.
5. Commit with `GITHUB_COMMIT_MULTIPLE_FILES` (`owner`, `repo`, `branch: main`, `message`, `upserts: [{path, content, encoding}]`).

## Adding images or other binaries
1. Build a zip of the files locally and give it to the human.
2. The human drags the zip into the repo on github.com (commit directly to `main`).
3. In the workbench, download it from its raw URL (the repo is public), check file hashes, commit the unpacked files as base64 with `GITHUB_COMMIT_MULTIPLE_FILES`, and delete the zip in the same or a follow-up commit.
Keep photos at 900x1200 JPG, named `photo-NN.jpg`, and add a smaller thumb for the picker.

## Verify after every push
- Check runs on the commit SHA (`GITHUB_LIST_CHECK_RUNS_FOR_A_REF`): wait for `build` and `deploy` to be `success`.
- Load the live page (browser pane or fetch with a cache-busting query string) and confirm the change is there. If the browser pane is hidden, lazy images will not load; that is not a site bug.

## Status and launch checklist
- Site is a draft: `index.html` has `<meta name="robots" content="noindex, nofollow">`. Remove it at launch.
- Domain not bought yet. Google Business Profile not set up yet.
- Owner control panel: Airtable base plus the scheduled sync described above (replaced the earlier Google Sheet plan). The base currently lives in the developer's personal Airtable workspace; transfer = make the owner a workspace Owner, then create a new read-only token under the new owner and replace the `AIRTABLE_TOKEN` secret.

## Rules
- Never paste or store API keys, tokens or passwords in the repo or chat. If one appears, tell the human to rotate it.
- Do not add personal data beyond what the business already publishes on its own site.
- Experimental work goes in its own folder (for example `/sheet-preview/`, noindex) so the live site is unaffected.
