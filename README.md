# Stylezz by Kam

One-page site for Stylezz by Kam (Edmonton, AB). Hosted free on GitHub Pages.

- Site: https://stylezzbykam.com/
- Photo picker: https://stylezzbykam.com/pick/

## Files

- `index.html` - the whole site. Prices, hours, gallery and a few text lines are generated from Airtable (see below); do not hand-edit those parts. Other facts (phone, address) are in the `SITE` object near the bottom and in the visible HTML text. Change both.
- `scripts/sync_airtable.py` and `.github/workflows/sync-airtable.yml` - the Airtable sync.
- `pick/index.html` - the photo picker Kamala uses to choose and tag her best photos.
- `assets/photos/` - full-size photos (photo-01.jpg and up).
- `assets/thumbs/` - small versions used only by the picker.
- `assets/logo.png` - logo.

## Updating the site

Prices, hours, photos and the price/payment/booking text: edit them in the Airtable interface "Update the website". A scheduled GitHub Action checks every 30 minutes and updates the site if anything changed (run it now from the Actions tab > Sync from Airtable > Run workflow). If a sync fails, the site simply keeps its last good version; the run's log says why. Setup needs the repo secret `AIRTABLE_TOKEN` (read-only Airtable token).

Anything else: any change pushed to `main` goes live in about a minute. Ask Claude to make the edit, or edit `index.html` on github.com with the pencil icon and press Commit.

## Launch checklist

- [x] Removed the `<meta name="robots" content="noindex, nofollow">` line (and the DRAFT comment after it) from `index.html` on 2026-10-13. The one in `pick/index.html` stays on purpose.
- [x] Prices added for boho braids, cornrows (with extensions) and male braids.
- [x] Cornrows (natural hair) $80, takedown $80 (+$20 small braids), wash and blow dry $40 confirmed.
- [ ] Confirm business name spelling ("Stylezz by Kam").
- [x] Applied Kamala's picks (STYLEZZ PICKS v1, 12 photos) to the Featured grid and tags.
- [x] Domain bought (stylezzbykam.com), DNS set, custom domain saved under Settings > Pages (this created the `CNAME` file).
- [ ] Tick Enforce HTTPS under Settings > Pages. The certificate exists, but plain http still serves and the old github.io address redirects to http (checked 2026-10-13).
- [x] `og:image` is an absolute https address on stylezzbykam.com.
- [x] Canonical tag added to `index.html` (`https://stylezzbykam.com/`), 2026-10-13.
- [x] Google Business Profile created (2026-10-13).
- [ ] Confirm the profile's website link is https://stylezzbykam.com/ (not the github.io address).
- [ ] Optional: add the site in Google Search Console and request indexing of the home page.
