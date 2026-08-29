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
 6. every locale carries both automatic-rate provider disclosures,
    attribution, free-tier and CSV/PDF/Photo export contracts.
"""
import hashlib
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import (  # noqa: E402
    APP_STORE_URL,
    BUILD_RECEIPT,
    CROSSPROMO,
    GENERATED_CSS,
    LOCALES,
    RTL,
    SHARED,
    SITE,
    canonical_url,
    load_disclosures,
    load_crosspromo,
    load_locales,
    route_path,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = ROOT.parent / "46_MoneyTag"
MAIL = "hourstag.app@gmail.com"
# built from parts so this file never contains the banned literal itself
BANNED = ("@" + "hotmail.com", "@" + "outlook.com")
PAGES = ("index.html", "privacy.html")
SURFACES = ("index", "support", "privacy")
FAIL = []
PLACEHOLDER_RE = re.compile(
    r"\{\{[^}]*\}\}|%[sd@]|\b(?:TODO|TBD|LOREM|PLACEHOLDER|XXX|undefined)\b"
)
RAW_KEY_RE = re.compile(
    r"\b(?:feature|button|screen|creator|privacy|support|nav|footer)"
    r"\.[a-z0-9_.-]+\b",
    re.I,
)
CLAIM_RE = re.compile(
    r"(?:\b#\s*1\b|\b4[.,]9\s*[★⭐]|\$\s*4[.,]99|"
    r"\bbest[- ]selling\b|\btop[- ]ranked\b)",
    re.I,
)


X_DEFAULT_TARGETS = {'index': '', 'support': '', 'privacy': 'privacy.html'}


def x_default_url(surface):
    """Root-level English equivalent of a surface, per upstream convention."""
    return SITE.rstrip("/") + "/" + X_DEFAULT_TARGETS.get(surface, "")


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


_ui_path = APP_ROOT / "assets" / "ui_i18n.json"
_ui = (
    json.loads(_ui_path.read_text(encoding="utf-8"))
    if _ui_path.is_file()
    else {}
)
UI_KEYS = (
    {
        key: {locale: _ui[language_group(locale)][key] for locale in LOCALES}
        for key in ("exportCsv", "exportPdf", "exportPhoto", "backupRestore")
    }
    if _ui
    else {}
)
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


SCRIPT_CHECKS = {
    "ar-SA": r"[\u0600-\u06ff]", "bn-BD": r"[\u0980-\u09ff]",
    "zh-Hans": r"[\u3400-\u9fff]", "zh-Hant": r"[\u3400-\u9fff]",
    "el": r"[\u0370-\u03ff]", "gu-IN": r"[\u0a80-\u0aff]",
    "he": r"[\u0590-\u05ff]", "hi": r"[\u0900-\u097f]",
    "ja": r"[\u3040-\u30ff\u3400-\u9fff]", "kn-IN": r"[\u0c80-\u0cff]",
    "ko": r"[\uac00-\ud7af]", "ml-IN": r"[\u0d00-\u0d7f]",
    "mr-IN": r"[\u0900-\u097f]", "or-IN": r"[\u0b00-\u0b7f]",
    "pa-IN": r"[\u0a00-\u0a7f]", "ru": r"[\u0400-\u04ff]",
    "ta-IN": r"[\u0b80-\u0bff]", "te-IN": r"[\u0c00-\u0c7f]",
    "th": r"[\u0e00-\u0e7f]", "uk": r"[\u0400-\u04ff]",
    "ur-PK": r"[\u0600-\u06ff]",
}


class SurfaceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_attrs = {}
        self.canonicals = []
        self.alternates = {}
        self.descriptions = []
        self.hrefs = []
        self.ld_json = []
        self.visible = []
        self._skip = 0
        self._ld = False
        self._ld_parts = []

    def handle_starttag(self, tag, attrs):
        values = {key.casefold(): value or "" for key, value in attrs}
        if tag == "html":
            self.html_attrs = values
        if tag in {"script", "style"}:
            self._skip += 1
        if tag == "link":
            rel = values.get("rel", "").casefold()
            if rel == "canonical":
                self.canonicals.append(values.get("href", ""))
            elif rel == "alternate":
                self.alternates.setdefault(
                    values.get("hreflang", ""), []
                ).append(values.get("href", ""))
        if (
            tag == "meta"
            and values.get("name", "").casefold() == "description"
        ):
            self.descriptions.append(values.get("content", ""))
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"])
        if (
            tag == "script"
            and values.get("type", "").casefold() == "application/ld+json"
        ):
            self._ld = True
            self._ld_parts = []

    def handle_endtag(self, tag):
        if tag == "script" and self._ld:
            self.ld_json.append("".join(self._ld_parts))
            self._ld = False
            self._ld_parts = []
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._ld:
            self._ld_parts.append(data)
        if not self._skip:
            value = " ".join(data.split())
            if value:
                self.visible.append(value)


def check_surface_links(path, parser, allowed_apps):
    for href in parser.hrefs:
        value = html.unescape(href).strip()
        if not value or value.startswith(("#", "mailto:", "tel:")):
            continue
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"}:
            if value in allowed_apps:
                continue
            if value.startswith(SITE):
                relative = unquote(value[len(SITE):])
                if not relative or relative.endswith("/"):
                    relative += "index.html"
                if not (ROOT / relative).is_file():
                    bad(f"{path.relative_to(ROOT)}: broken same-site link {value}")
                continue
            bad(f"{path.relative_to(ROOT)}: unverified external link {value}")
            continue
        if parsed.scheme or parsed.netloc:
            bad(f"{path.relative_to(ROOT)}: unsupported link {value}")
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        if ROOT not in target.parents and target != ROOT:
            bad(f"{path.relative_to(ROOT)}: link escapes repository {value}")
        elif not target.is_file():
            bad(f"{path.relative_to(ROOT)}: broken local link {value}")


def check_surface_page(locale, surface, allowed_apps, promo_urls):
    path = route_path(locale, surface)
    if not path.is_file():
        bad(f"{locale}/{surface}: missing required surface")
        return ""
    raw = path.read_text(encoding="utf-8")
    parser = SurfaceParser()
    parser.feed(raw)
    parser.close()
    visible = re.sub(r"\s+", " ", " ".join(parser.visible)).strip()
    canonical = canonical_url(locale, surface)
    expected_dir = "rtl" if locale in RTL else "ltr"
    if parser.html_attrs.get("lang") != locale:
        bad(f"{path.relative_to(ROOT)}: html lang mismatch")
    if parser.html_attrs.get("dir") != expected_dir:
        bad(f"{path.relative_to(ROOT)}: html dir mismatch")
    if parser.canonicals != [canonical]:
        bad(f"{path.relative_to(ROOT)}: canonical mismatch")
    if len(parser.descriptions) != 1 or not parser.descriptions[0].strip():
        bad(f"{path.relative_to(ROOT)}: meta description mismatch")
    expected_hreflang = set(LOCALES) | {"x-default"}
    if set(parser.alternates) != expected_hreflang:
        bad(f"{path.relative_to(ROOT)}: hreflang set mismatch")
    for hreflang, values in parser.alternates.items():
        expected = (
            x_default_url(surface)
            if hreflang == "x-default"
            else canonical_url(hreflang, surface)
        )
        if values != [expected]:
            bad(f"{path.relative_to(ROOT)}: {hreflang} alternate mismatch")
    if not parser.ld_json:
        bad(f"{path.relative_to(ROOT)}: JSON-LD missing")
    schema_ok = False
    for block in parser.ld_json:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            bad(f"{path.relative_to(ROOT)}: invalid JSON-LD")
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        if any(
            isinstance(candidate, dict)
            and candidate.get("@context") == "https://schema.org"
            and candidate.get("inLanguage") == locale
            and candidate.get("url") == canonical
            for candidate in candidates
        ):
            schema_ok = True
        encoded = json.dumps(payload, ensure_ascii=False)
        if any(
            key in encoded
            for key in ("aggregateRating", "ratingValue", "reviewCount")
        ) or re.search(r'"offers"\s*:\s*\{[^}]*"price"', encoded):
            bad(f"{path.relative_to(ROOT)}: fabricated schema claim")
    if not schema_ok:
        bad(f"{path.relative_to(ROOT)}: locale-bound schema missing")
    if raw.count('data-surface-crosspromo="true"') != 1:
        bad(f"{path.relative_to(ROOT)}: cross-promo section mismatch")
    promo_match = re.search(
        r'<section\b[^>]*data-surface-crosspromo=["\']true["\'][^>]*>'
        r"(.*?)</section>",
        raw,
        re.I | re.S,
    )
    actual_promo = (
        {
            html.unescape(value)
            for value in re.findall(
                r'<a\b[^>]*href=["\']([^"\']+)["\']',
                promo_match.group(1),
                re.I,
            )
        }
        if promo_match
        else set()
    )
    if actual_promo != promo_urls:
        bad(f"{path.relative_to(ROOT)}: cross-promo URL mismatch")
    if (
        raw.count('data-surface-own-app="true"') != 1
        or APP_STORE_URL not in parser.hrefs
    ):
        bad(f"{path.relative_to(ROOT)}: verified own-app CTA missing")
    for href in parser.hrefs:
        value = html.unescape(href)
        if "apps.apple.com/" in value and value not in allowed_apps:
            bad(f"{path.relative_to(ROOT)}: unverified App Store URL {value}")
    if MAIL not in raw or MAIL not in visible:
        bad(f"{path.relative_to(ROOT)}: contact email missing")
    if PLACEHOLDER_RE.search(visible) or RAW_KEY_RE.search(visible):
        bad(f"{path.relative_to(ROOT)}: raw key or placeholder found")
    if re.search(r"\bnull\b", visible) or "\ufffd" in visible:
        bad(f"{path.relative_to(ROOT)}: broken visible localization token")
    if CLAIM_RE.search(visible):
        bad(f"{path.relative_to(ROOT)}: unverified price/rating/ranking claim")
    if locale in SCRIPT_CHECKS and not re.search(
        SCRIPT_CHECKS[locale], visible
    ):
        bad(f"{path.relative_to(ROOT)}: expected native script missing")
    check_surface_links(path, parser, allowed_apps)
    return visible


def check_surface_receipt():
    if not BUILD_RECEIPT.is_file():
        bad("surface-build.json missing")
        return
    receipt = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
    records = receipt.get("files", {})
    required = {
        str(route_path(locale, surface).relative_to(ROOT))
        for locale in LOCALES
        for surface in SURFACES
    }
    if receipt.get("officialLocaleCount") != 50:
        bad("surface-build.json locale count mismatch")
    if receipt.get("requiredSurfaceCount") != 150:
        bad("surface-build.json required surface count mismatch")
    if not required.issubset(records):
        bad("surface-build.json omits required surfaces")
    actual = {}
    for relative, expected in records.items():
        path = ROOT / relative
        if not path.is_file():
            bad(f"surface-build.json references missing {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        actual[relative] = digest
        if digest != expected:
            bad(f"surface-build.json SHA mismatch for {relative}")
    digest = hashlib.sha256(
        json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != receipt.get("contentDigest"):
        bad("surface-build.json content digest mismatch")


def check_required_surfaces():
    data = load_locales()
    _, apps = load_crosspromo()
    promo_urls = {app["url"] for app in apps}
    allowed_apps = promo_urls | {APP_STORE_URL}
    visible = {}
    locale_dirs = {
        path.parent.name
        for path in ROOT.glob("*/*.html")
        if path.name in {"index.html", "support.html", "privacy.html"}
    }
    if locale_dirs != set(LOCALES):
        bad(
            "required locale directory mismatch: "
            f"missing={sorted(set(LOCALES)-locale_dirs)} "
            f"extra={sorted(locale_dirs-set(LOCALES))}"
        )
    for locale in LOCALES:
        for surface in SURFACES:
            visible[(locale, surface)] = check_surface_page(
                locale, surface, allowed_apps, promo_urls
            )
    for surface in SURFACES:
        baseline = visible.get(("en-US", surface), "")
        for locale in LOCALES:
            if locale.startswith("en-"):
                continue
            if baseline and visible.get((locale, surface)) == baseline:
                bad(f"{locale}/{surface}: copied English fallback")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    sitemap_urls = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
    for locale in LOCALES:
        for surface in SURFACES:
            expected = canonical_url(locale, surface)
            if expected not in sitemap_urls:
                bad(f"sitemap.xml missing {expected}")
    if not GENERATED_CSS.is_file():
        bad("surface-generated.css missing")
    check_surface_receipt()


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
        for anchor in ("Frankfurter", "ExchangeRate-API"):
            if anchor not in disclosure_fields["currency FAQ"]:
                bad(f"{code}: currency FAQ missing {anchor}")
        for label in ("storage FAQ", "network FAQ", "privacy vow", "network policy", "rate policy"):
            value = disclosure_fields[label]
            for anchor in (
                "api.frankfurter.dev",
                "open.er-api.com",
                "Frankfurter",
                "ExchangeRate-API",
            ):
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
        if _ui:
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
    allowed_external = {
        html.unescape(url)
        for url in re.findall(
            r"https?://[^\"'\s)]+",
            CROSSPROMO.read_text(encoding="utf-8"),
        )
    }
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
            normalized = html.unescape(url)
            if (
                not normalized.startswith(SITE.rstrip("/"))
                and normalized not in allowed_external
            ):
                bad(f"{name}: external reference {normalized}")
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
    banned_hosts = ("api.frankfurter." + "app",)
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
        "api.frankfurter.dev", "open.er-api.com", "exchangerate-api",
        "cloudflare", "ip address",
        "may be linked to you", "not used for tracking", "no advertising",
        "provided by frankfurter or exchangerate-api",
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
    check_required_surfaces()
    check_mail()
    check_legacy_providers()
    check_honesty()
    if FAIL:
        for msg in FAIL:
            print("FAIL", msg)
        sys.exit(1)
    print(
        f"PASS  {len(LOCALES)} locales, 150 required surfaces, "
        f"{len(PAGES)} preserved root pages, contact {MAIL}"
    )


if __name__ == "__main__":
    main()
