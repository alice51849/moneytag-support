# MoneyTag — Official Support & Privacy Site

Static support and privacy site for the iOS app **MoneyTag: Income & Expense**
(project-based two-way income/expense tracking, source at `~/46_MoneyTag`).
Live URL: `https://alice51849.github.io/moneytag-support/`

Each project has its own base currency. On the Home screen, a user can choose
the input currency, use public automatic rates refreshed about every six hours,
set a manual rate, or reset to automatic. Converted amounts are saved in the
project's base currency, and saved rates remain available offline. The public
rate services require no API key and receive no ledger or personal data.

每個專案都有自己的基準幣別。使用者可直接在首頁選擇輸入幣別，使用約每六小時更新的公開自動匯率，
也可設定手動匯率或還原為自動。換算後以專案的基準幣別儲存，已儲存的匯率離線時仍可使用。
公開匯率服務不需要 API 金鑰，也不會收到帳務或個人資料。

- `index.html` — support page + FAQ (9 questions per locale)
- `privacy.html` — privacy policy (9 sections per locale)
- Pure-JS language switcher for all **50 Apple product-page locales**
- The website itself has no CDNs, external requests, web fonts, analytics or
  cookies — inline CSS + inline JS only
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
tools/sync_app_contract.py  syncs the 5-entry and CSV/PDF rules from the app
assets/icon.png          app icon (512 px, from ~/46_MoneyTag/assets/app-icon.png)
```

`index.html` and `privacy.html` are **generated** — edit `src/`, never the built pages.

## Build & validate

```bash
cd ~/46_moneytag-support
~/00_GrowthEngine/.venv/bin/python tools/sync_app_contract.py
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
5. the website itself references no external host,
6. every locale accurately discloses automatic/manual exchange rates, offline
   saved rates, both public rate services, on-device ledger data and Apple's
   separate purchase/restore handling.

## Locale coverage

All **50** Apple product-page locales ship — the same set the app declares in
`CFBundleLocalizations` — and `tools/build.py` has an empty `PENDING` list.
To add another later: write its block into a `src/locales/part-*.json` chunk,
add the code to `LOCALES`, then run `build.py` and `check.py`.

## Publishing

The public repository is `alice51849/moneytag-support`, with GitHub Pages
publishing the `main` branch root.

```bash
cd ~/46_moneytag-support
git push origin main
gh api repos/alice51849/moneytag-support/pages --jq '.status, .html_url'
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
- Every project has its own base currency. The Home screen accepts a selected
  input currency and converts it with public automatic rates refreshed about
  every six hours, or a manual rate that can later be reset to automatic.
  Converted amounts are stored in the project's base currency; saved rates work
  offline.
- Projects, transactions, tags and settings stay on device. There is no
  account, advertising, analytics, tracking or third-party SDK.
- The only non-Apple network use is fetching public exchange-rate quotes from
  keyless services: `open.er-api.com` is primary and `api.frankfurter.app` is
  fallback. No transaction, project, tag, setting or personal data is sent.
- Free tier: 1 project + 5 transactions. Lifetime Pro is a one-time purchase
  (never a subscription) unlocking unlimited projects and transactions,
  cross-project tag analysis, custom categories and tags, CSV/PDF export,
  backup and restore.
- Apple Watch app and Home Screen / Lock Screen widgets read on-device data
  through Apple's app group and Watch Connectivity only.
- In-app purchases and restores are handled entirely by Apple.
