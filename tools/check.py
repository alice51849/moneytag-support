#!/usr/bin/env python3
"""Validate the MoneyTag support site. Prints PASS or exits non-zero.

Checks:
 1. every shipped locale exists with complete support + privacy content,
 2. every FAQ / policy entry is a non-empty [heading, body] pair,
 3. both built pages embed every shipped locale in the switcher payload,
 4. the only public contact address anywhere in the repo is
    hourstag.app@gmail.com (AGENTS.md rule 32 — the private hotmail address is
    banned from any public-facing material),
 5. no page references an external host, and the site claims nothing the app
    does not do (honesty guard on the offline / no-tracking wording).
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import LOCALES, SHARED, SITE, load_locales  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAIL = "hourstag.app@gmail.com"
# built from parts so this file never contains the banned literal itself
BANNED = ("@" + "hotmail.com", "@" + "outlook.com")
PAGES = ("index.html", "privacy.html")
FAIL = []


def bad(msg):
    FAIL.append(msg)


def check_content():
    data = load_locales()
    for code in LOCALES:
        t = data[code]
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


def check_honesty():
    """The site may only make claims that hold for the shipped app."""
    data = load_locales()
    en = data["en-US"]
    joined = json.dumps(en, ensure_ascii=False).lower()
    must = ["one-time purchase", "no network requests", "30 transactions", "one project"]
    for phrase in must:
        if phrase not in joined:
            bad(f"en-US: honesty anchor missing — {phrase!r}")
    for forbidden in ["free forever unlimited", "bank sync", "automatic import",
                      "encrypted cloud", "military-grade"]:
        if forbidden in joined:
            bad(f"en-US: claim the app does not support — {forbidden!r}")


def main():
    check_content()
    check_pages()
    check_mail()
    check_honesty()
    if FAIL:
        for msg in FAIL:
            print("FAIL", msg)
        sys.exit(1)
    print(f"PASS  {len(LOCALES)} locales, {len(PAGES)} pages, contact {MAIL}")


if __name__ == "__main__":
    main()
