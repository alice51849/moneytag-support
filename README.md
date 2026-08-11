# MoneyTag — Official Support & Privacy Site

Static support and privacy site for the iOS app **MoneyTag: Income & Expense**
(project-based two-way income/expense tracking, source at `~/47_MoneyTag`).
Target URL once published: `https://alice51849.github.io/moneytag-support/`

- `index.html` — support page + FAQ (9 questions per locale)
- `privacy.html` — privacy policy (9 sections per locale)
- Language switcher in pure JS: **English, 繁體中文, 简体中文, 日本語, 한국어**
  (any other App Store locale resolves to the closest of these, then English)
- No CDNs, no external requests, no web fonts, no analytics, no cookies —
  inline CSS + inline JS only
- Contact address everywhere: `hourstag.app@gmail.com`

Visual system matches the app's **Ledger Glass** design: warm bright glass on a
never-flat warm-gold/green/teal wash, income green `#1F9D63`, expense coral
`#D9614F`, warm-gold glow `#C9A227`, light and dark themes.

## Per-locale URLs (for App Store Connect)

Each locale's `supportUrl` / `privacyPolicyUrl` can carry the language:

```
https://alice51849.github.io/moneytag-support/?lang=ja
https://alice51849.github.io/moneytag-support/privacy.html?lang=ja
```

Without `?lang=`, the page auto-detects from `navigator.languages`, remembers
the last choice in `localStorage`, and falls back to `en-US`.

## Repository layout

```
src/style.css            shared stylesheet (Ledger Glass palette)
src/app.js               locale renderer (vanilla JS, no dependencies)
src/page.tpl.html        page shell used for both pages
src/locales/part-en.json    en-US
src/locales/part-cjk.json   zh-Hant, zh-Hans, ja, ko
src/locales/part-eu.json    28 European locales (de-DE … en-CA)
src/locales/part-asia.json  17 Asian / RTL locales (ar-SA, he, hi … ur-PK)
tools/build.py           merges locales + CSS + JS into index.html / privacy.html
tools/check.py           validation (locales, contact address, no external hosts)
assets/icon.png          app icon (512 px, from ~/47_MoneyTag/assets/app-icon.png)
```

`index.html` and `privacy.html` are **generated** — edit `src/`, never the built pages.

## Build & validate

```bash
cd ~/47_moneytag-support
~/00_GrowthEngine/.venv/bin/python tools/build.py     # regenerate both pages
~/00_GrowthEngine/.venv/bin/python tools/check.py     # must print PASS
```

`check.py` asserts:
1. every shipped locale has complete support + privacy content, with the same
   number of FAQ entries and policy sections as English,
2. every FAQ / policy entry is a non-empty pair,
3. both built pages embed every shipped locale in the switcher payload,
4. the banned private mail domain appears nowhere in the repository — the only
   public contact address is `hourstag.app@gmail.com` (AGENTS.md rule 32),
5. no page references any external host and no honesty-breaking claim
   (bank sync, automatic import, encrypted cloud …) appears.

## Locale coverage

All **50** Apple product-page locales ship — the same set the app declares in
`CFBundleLocalizations` — and `tools/build.py` has an empty `PENDING` list.
To add another later: write its block into a `src/locales/part-*.json` chunk,
add the code to `LOCALES`, then run `build.py` and `check.py`.

## Publishing (NOT done yet — outward-facing, needs owner approval)

No git repository, no remote and no deployment exists for this directory yet.

```bash
cd ~/47_moneytag-support
git init -b main
git add .
git commit -m "MoneyTag support and privacy site"

# create the public repo and push
gh repo create alice51849/moneytag-support --public --source=. --remote=origin --push

# enable GitHub Pages from the main branch root
gh api -X POST repos/alice51849/moneytag-support/pages \
  -f 'source[branch]=main' -f 'source[path]=/'

# verify (allow a minute for the first build)
gh api repos/alice51849/moneytag-support/pages --jq '.status, .html_url'
curl -sI https://alice51849.github.io/moneytag-support/ | head -1
```

After the site is live, set every locale's `supportUrl` and `privacyPolicyUrl`
in App Store Connect to the `?lang=<locale>` form above (missing URLs block
review), and make sure the privacy URL inside the app points at the live page.

## Editing content

1. Change the relevant `src/locales/part-*.json` entry.
2. Run `build.py`, then `check.py`.
3. Bump `UPDATED` in `tools/build.py` **and** `src/app.js` if the privacy text
   changed (both hold the same date string shown as "Last updated"), and the
   `lastmod` dates in `sitemap.xml`.

## Honesty constraints (these must stay true of the app)

- Project-based two-way ledger: each project computes income − expenses = net.
- Tags are first-class and roll up income / expense / net across projects.
- One currency per project; **no exchange rates, no currency conversion** —
  amounts are exactly the numbers the user typed.
- Fully offline: zero network requests, no third-party SDK, no ads, no
  analytics, no tracking; all data stays on device.
- Free tier: 1 project + 30 transactions. Lifetime Pro is a one-time purchase
  (never a subscription) unlocking unlimited projects and transactions,
  cross-project tag analysis, custom categories and tags, CSV/text export,
  backup and restore.
- Apple Watch app and Home Screen / Lock Screen widgets read on-device data
  through Apple's app group and Watch Connectivity only.
- Purchases and restores are handled entirely by Apple.
