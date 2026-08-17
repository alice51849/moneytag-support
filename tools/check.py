#!/usr/bin/env python3
"""Validate the MoneyTag support site. Prints PASS or exits non-zero.

Checks:
 1. every shipped locale exists with complete support + privacy content,
 2. every FAQ / policy entry is a non-empty [heading, body] pair,
 3. both built pages embed every shipped locale in the switcher payload,
 4. the only public contact address anywhere in the repo is
    hourstag.app@gmail.com (AGENTS.md rule 32 — the private hotmail address is
    banned from any public-facing material),
 5. the website itself references no external host,
 6. every locale carries the Frankfurter-only network/privacy disclosure,
    attribution, free-tier and CSV/PDF export contracts.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import (  # noqa: E402
    LOCALES,
    SHARED,
    SITE,
    load_disclosures,
    load_locales,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = ROOT.parent / "46_MoneyTag"
MAIL = "hourstag.app@gmail.com"
# built from parts so this file never contains the banned literal itself
BANNED = ("@" + "hotmail.com", "@" + "outlook.com")
PAGES = ("index.html", "privacy.html")
FAIL = []


def language_group(locale):
    if locale.startswith("en-"):
        return "en"
    if locale.startswith("fr-"):
        return "fr"
    if locale.startswith("es-"):
        return "es"
    if locale.startswith("pt-"):
        return "pt"
    exact = {
        "zh-Hans": "zh-Hans", "zh-Hant": "zh-Hant",
        "de-DE": "de", "nl-NL": "nl", "bn-BD": "bn", "gu-IN": "gu",
        "kn-IN": "kn", "ml-IN": "ml", "mr-IN": "mr", "or-IN": "or",
        "pa-IN": "pa", "sl-SI": "sl", "ta-IN": "ta", "te-IN": "te",
        "ur-PK": "ur",
    }
    return exact.get(locale, locale.split("-", 1)[0])


_ui = json.loads((APP_ROOT / "assets" / "ui_i18n.json").read_text(encoding="utf-8"))
UI_KEYS = {
    key: {locale: _ui[language_group(locale)][key] for locale in LOCALES}
    for key in ("exportCsv", "exportPdf", "backupRestore")
}
PRIVACY_UI_KEYS = {
    "privacyNote": "ledger",
    "onboardFootnote": "summary",
    "privacyRequestNote": "request",
    "privacyNetworkNote": "processing",
    "privacyUseNote": "use",
    "privacyManualNote": "manual",
    "rateAttribution": "attribution",
}


def bad(msg):
    FAIL.append(msg)


def check_content():
    data = load_locales()
    disclosures = load_disclosures()
    for code in LOCALES:
        t = data[code]
        disclosure = disclosures[code]
        for key in SHARED:
            if not t.get(key):
                bad(f"{code}: missing shared key {key}")
        if len(t.get("nav", [])) != 2:
            bad(f"{code}: nav must hold two labels")
        s, p = t.get("s", {}), t.get("p", {})
        for key in ("title", "meta", "eyebrow", "h1", "lead", "faqT", "cT", "cL", "cB"):
            if not s.get(key):
                bad(f"{code}: support block missing {key}")
        for key in ("title", "meta", "eyebrow", "h1", "lead", "upd", "vow", "cT", "cL", "cB"):
            if not p.get(key):
                bad(f"{code}: privacy block missing {key}")
        if len(s.get("chips", [])) < 4:
            bad(f"{code}: needs at least four chips")
        if len(s.get("faq", [])) < 6:
            bad(f"{code}: needs at least six FAQ entries")
        if len(p.get("sec", [])) < 6:
            bad(f"{code}: needs at least six policy sections")
        for label, rows in (("faq", s.get("faq", [])), ("sec", p.get("sec", []))):
            for i, row in enumerate(rows, 1):
                if len(row) != 2 or not row[0].strip() or not row[1].strip():
                    bad(f"{code}: {label} entry {i} is not a filled pair")
        workflow = s.get("faq", [[], []])[1][1]
        attribution = disclosure["attribution"]
        base_workflow = (
            workflow[:-len(attribution)].rstrip()
            if workflow.endswith(attribution)
            else workflow
        )
        if "6" not in workflow:
            bad(f"{code}: currency FAQ must disclose the roughly six-hour refresh")
        if not code.startswith("en-") and workflow == data["en-US"]["s"]["faq"][1][1]:
            bad(f"{code}: currency FAQ is copied from English")
        free_answer = s.get("faq", [[], [], [], [None, ""]])[3][1]
        watch_answer = s.get("faq", [[], [], [], [], [], [], [None, ""]])[6][1]
        export_answer = s.get(
            "faq", [[], [], [], [], [], [], [], [], [None, ""]]
        )[8][1]
        if "10" in free_answer or "30" in free_answer or "5" not in free_answer:
            bad(f"{code}: free tier must be exactly five transactions")
        for label in ("exportCsv", "exportPdf", "backupRestore"):
            if label not in UI_KEYS:
                continue
            if UI_KEYS[label][code] not in free_answer:
                bad(f"{code}: free/Pro FAQ missing localized {label}")
            if UI_KEYS[label][code] not in export_answer:
                bad(f"{code}: export FAQ missing localized {label}")
        if disclosure["ledger"] not in watch_answer:
            bad(f"{code}: Watch FAQ still uses an absolute no-network claim")
        disclosure_fields = {
            "currency FAQ": s.get("faq", [[], []])[1][1],
            "storage FAQ": s.get("faq", [[], [], [], [], [], [None, ""]])[5][1],
            "network FAQ": s.get("faq", [[], [], [], [], [], [], [], [None, ""]])[7][1],
            "privacy vow": p.get("vow", ""),
            "network policy": p.get("sec", [[], []])[1][1],
            "rate policy": p.get("sec", [[], [], [], [None, ""]])[3][1],
        }
        if "Frankfurter" not in disclosure_fields["currency FAQ"]:
            bad(f"{code}: currency FAQ missing Frankfurter")
        for label in ("storage FAQ", "network FAQ", "privacy vow", "network policy", "rate policy"):
            value = disclosure_fields[label]
            for anchor in ("api.frankfurter.dev", "Frankfurter"):
                if anchor not in value:
                    bad(f"{code}: {label} missing {anchor}")
        for label in ("storage FAQ", "network FAQ", "privacy vow", "network policy", "rate policy"):
            for anchor in ("Cloudflare", "IP"):
                if anchor not in disclosure_fields[label]:
                    bad(f"{code}: {label} missing {anchor}")
        if attribution not in disclosure_fields["currency FAQ"]:
            bad(f"{code}: currency FAQ missing localized attribution")
        if base_workflow not in disclosure_fields["rate policy"]:
            bad(f"{code}: rate policy is not synchronized with the currency FAQ")
        ui = _ui[language_group(code)]
        for ui_key, disclosure_key in PRIVACY_UI_KEYS.items():
            if ui.get(ui_key) != disclosure[disclosure_key]:
                bad(f"{code}: App {ui_key} differs from support disclosure")
        source = json.dumps(t, ensure_ascii=False)
        if "G+Money" in source:
            bad(f"{code}: G+Money branding leaked into MoneyTag copy")
    # every locale must carry the same number of FAQ entries as English
    n = len(data["en-US"]["s"]["faq"])
    for code in LOCALES:
        if len(data[code]["s"]["faq"]) != n:
            bad(f"{code}: {len(data[code]['s']['faq'])} FAQ entries, English has {n}")
    m = len(data["en-US"]["p"]["sec"])
    for code in LOCALES:
        if len(data[code]["p"]["sec"]) != m:
            bad(f"{code}: {len(data[code]['p']['sec'])} policy sections, English has {m}")


def check_pages():
    for name in PAGES:
        f = ROOT / name
        if not f.exists():
            bad(f"{name} not built — run tools/build.py")
            continue
        text = f.read_text(encoding="utf-8")
        payload = re.search(r"window\.MONEYTAG_I18N=(\{.*?\});", text, re.S)
        if not payload:
            bad(f"{name}: locale payload not found")
        else:
            embedded = json.loads(payload.group(1).replace("<\\/", "</"))
            for code in LOCALES:
                if code not in embedded:
                    bad(f"{name}: locale {code} missing from the switcher")
        if MAIL not in text:
            bad(f"{name}: contact address missing")
        # external hosts: only this site's own canonical / og URLs are allowed
        for url in re.findall(r"https?://[^\"'\s)]+", text):
            if not url.startswith(SITE.rstrip("/")):
                bad(f"{name}: external reference {url}")
        for tag in ("<script src=", "<link rel=\"stylesheet\"", "@import", "fetch(",
                    "XMLHttpRequest", "googletagmanager", "google-analytics"):
            if tag in text:
                bad(f"{name}: forbidden external/tracking construct {tag!r}")


def check_mail():
    for f in ROOT.rglob("*"):
        if not f.is_file() or ".git/" in str(f) or f.suffix in (".png", ".jpg", ".pyc"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for banned in BANNED:
            if banned in text:
                bad(f"{f.relative_to(ROOT)}: banned contact address {banned}")
        for addr in set(re.findall(r"[\w.+-]+@[\w.-]+\.\w+", text)):
            if addr != MAIL:
                bad(f"{f.relative_to(ROOT)}: unexpected address {addr}")


def check_legacy_providers():
    banned_hosts = ("open." + "er-api.com", "api.frankfurter." + "app")
    for f in ROOT.rglob("*"):
        if (
            not f.is_file()
            or ".git/" in str(f)
            or f.suffix in (".png", ".jpg", ".pyc")
        ):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for host in banned_hosts:
            if host in text:
                bad(f"{f.relative_to(ROOT)}: legacy exchange-rate host {host}")


def check_honesty():
    """The site may only make claims that hold for the shipped app."""
    data = load_locales()
    en = data["en-US"]
    joined = json.dumps(en, ensure_ascii=False).lower()
    must = [
        "one purchase", "5 entries left", "1 project", "base currency",
        "manual rate", "reset to automatic", "saved rates",
        "api.frankfurter.dev", "cloudflare", "ip address",
        "may be linked to you", "not used for tracking", "no advertising",
        "european central bank data via frankfurter",
    ]
    for phrase in must:
        if phrase not in joined:
            bad(f"en-US: honesty anchor missing — {phrase!r}")
    stale_claims = [
        "no exchange " + "rates",
        "no currency " + "conversion",
        "never applies an exchange " + "rate",
        "no network " + "requests",
        "zero network " + "requests",
        "no data collected",
        "data we collect: none",
        "everything stays on your device",
        "nothing travels over the internet",
    ]
    for forbidden in [
        "free forever unlimited", "bank sync", "automatic import",
        "encrypted cloud", "military-grade", "daily budget", "family trip",
        *stale_claims,
    ]:
        if forbidden in joined:
            bad(f"en-US: claim the app does not support — {forbidden!r}")


def main():
    check_content()
    check_pages()
    check_mail()
    check_legacy_providers()
    check_honesty()
    if FAIL:
        for msg in FAIL:
            print("FAIL", msg)
        sys.exit(1)
    print(f"PASS  {len(LOCALES)} locales, {len(PAGES)} pages, contact {MAIL}")


if __name__ == "__main__":
    main()
