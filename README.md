# Stylezz by Kam

One-page site for Stylezz by Kam (Edmonton, AB). Hosted free on GitHub Pages.

- Site: https://stylezzbykam.github.io
- Photo picker: https://stylezzbykam.github.io/pick/

## Files

- `index.html` - the whole site. Business facts (hours, prices, phone) are in the `SITE` object near the bottom and in the visible HTML text. Change both.
- `pick/index.html` - the photo picker Kamala uses to choose and tag her best photos.
- `assets/photos/` - full-size photos (photo-01.jpg and up).
- `assets/thumbs/` - small versions used only by the picker.
- `assets/logo.png` - logo.

## Updating the site

Any change pushed to `main` goes live in about a minute. Ask Claude to make the edit, or edit `index.html` on github.com with the pencil icon and press Commit.

## Launch checklist

- [ ] Remove the `<meta name="robots" content="noindex, nofollow">` line (and the DRAFT comment after it) from `index.html`. Keep the one in `pick/index.html`.
- [x] Prices added for boho braids, cornrows (with extensions) and male braids.
- [ ] Confirm price for cornrows on natural hair, and takedown wording.
- [ ] Confirm business name spelling ("Stylezz by Kam").
- [x] Applied Kamala's picks (STYLEZZ PICKS v1, 12 photos) to the Featured grid and tags.
- [ ] Buy the domain, then add a `CNAME` file and set the custom domain under Settings > Pages. Turn on Enforce HTTPS.
- [ ] Make the `og:image` URL absolute (full https address) so link previews work.
- [ ] Update the website link on the Google Business Profile.
