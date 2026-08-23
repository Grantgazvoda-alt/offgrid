# OffGrid site — maintenance

This repo builds the GitHub Pages site (grantgazvoda-alt.github.io/offgrid-site).

## Activating the waitlist backend (Formspree)
The calculator already POSTs to `WAITLIST_URL` when set (FormData + honeypot
`_gotcha`, Formspree-compatible). To go live:
1. Create a free form at formspree.io (account → New form).
2. Copy its endpoint (https://formspree.io/f/xxxx).
3. In `roi.html` set `var WAITLIST_URL = "https://formspree.io/f/xxxx";`
4. Submit once — Formspree emails YOU a confirmation link; click it to activate.
Until then the calculator falls back to prefilled-mailto (works, zero setup).

## Waitlist counter
Source of truth is `waitlist.json` (count/goal). Both index.html and roi.html
read it. As signups land (Formspree inbox), bump `count` here and push — the
Pages rebuild updates both pages. count defaults 0 (honest), goal 100.

## Analytics
All off by default. In index.html:
- GA4:        `ANALYTICS_PROVIDER = "ga4"` + `GA4_ID = "G-…"`
- Plausible:  `ANALYTICS_PROVIDER = "plausible"` + `PLAUSIBLE_DOMAIN` (the domain
  registered in your Plausible account; self-hosted? also set `PLAUSIBLE_SRC`).
Custom event `waitlist_submit` (with tier + est savings) fires on both providers.
