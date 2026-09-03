#!/usr/bin/env python3
"""Build the MoneyTag support site.

Merges src/locales/*.json into two fully self-contained pages:
  index.html   -> support + FAQ
  privacy.html -> privacy policy

Each page carries inline CSS, inline JS and only the locale strings that page
needs. No external requests of any kind are emitted.
"""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DISCLOSURES = SRC / "privacy_disclosures.json"

# Locales shipped on the site today. The renderer resolves any other App Store
# locale to the closest one of these (English last), so ?lang=<anything> works.
LOCALES = [
    "en-US", "zh-Hant", "zh-Hans", "ja", "ko", "de-DE", "fr-FR", "fr-CA",
    "es-ES", "es-MX", "it", "pt-BR", "pt-PT", "nl-NL", "sv", "da", "fi",
    "no", "ru", "pl", "tr", "cs", "sk", "hr", "hu", "ro", "uk", "el", "ca",
    "sl-SI", "en-GB", "en-AU", "en-CA", "ar-SA", "he", "hi", "th", "vi",
    "id", "ms", "bn-BD", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "or-IN",
    "pa-IN", "ta-IN", "te-IN", "ur-PK",
]

# Remaining Apple product-page locales, still to be written before the global
# launch (§ localization.md). Add a src/locales/part-*.json chunk, then list the
# code here-to-there: move it from PENDING into LOCALES.
PENDING = []
RTL = {"ar-SA", "he", "ur-PK"}
SITE = "https://open.cait518.cc/moneytag-support/"
UPDATED = "2026-08-17"
SHARED = ("n", "l", "tag", "nav", "lang", "foot", "store")
DISCLOSURE_KEYS = (
    "summary", "ledger", "request", "processing", "use", "manual",
    "attribution", "networkTitle", "delete", "changes",
)


def load_disclosures():
    payload = json.loads(DISCLOSURES.read_text(encoding="utf-8"))
    keys = tuple(payload.get("keys", ()))
    locale_groups = payload.get("localeGroups", {})
    raw_groups = payload.get("groups", {})
    if keys != DISCLOSURE_KEYS:
        sys.exit(
            f"privacy disclosure keys must be: {', '.join(DISCLOSURE_KEYS)}"
        )
    groups = {}
    for group, values in raw_groups.items():
        if not isinstance(values, list) or len(values) != len(keys):
            sys.exit(f"privacy disclosure group {group} has invalid field count")
        groups[group] = dict(zip(keys, values))
    if set(locale_groups) != set(LOCALES):
        sys.exit(
            "privacy disclosure locale mismatch: "
            f"missing={set(LOCALES)-set(locale_groups)} "
            f"extra={set(locale_groups)-set(LOCALES)}"
        )
    used_groups = set(locale_groups.values())
    if used_groups != set(groups):
        sys.exit(
            "privacy disclosure group mismatch: "
            f"missing={used_groups-set(groups)} extra={set(groups)-used_groups}"
        )
    for group, value in groups.items():
        missing = [
            key for key in DISCLOSURE_KEYS
            if not isinstance(value.get(key), str) or not value[key].strip()
        ]
        if missing:
            sys.exit(f"privacy disclosure group {group} missing: {', '.join(missing)}")
        if any("\n" in value[key] or "\r" in value[key] for key in DISCLOSURE_KEYS):
            sys.exit(f"privacy disclosure group {group} contains a line break")
        if group != "en":
            fallbacks = [
                key for key in DISCLOSURE_KEYS
                if value[key] == groups["en"][key]
            ]
            if fallbacks:
                sys.exit(
                    f"privacy disclosure group {group} uses English fallback: "
                    f"{', '.join(fallbacks)}"
                )
    return {
        locale: groups[group]
        for locale, group in locale_groups.items()
    }


def disclosure_network(value):
    return " ".join((value["request"], value["processing"], value["use"]))


def privacy_contract_errors(data, disclosures):
    errors = []
    for locale in LOCALES:
        entry = data[locale]
        support = entry["s"]
        privacy = entry["p"]
        value = disclosures[locale]
        attribution = value["attribution"]
        workflow = support["faq"][1][1]
        if workflow.endswith(attribution):
            workflow = workflow[:-len(attribution)].rstrip()
        network = disclosure_network(value)
        expected = {
            "foot": value["summary"],
            "support meta": value["summary"],
            "currency FAQ": " ".join((workflow, attribution)),
            "storage FAQ": " ".join((
                value["ledger"], network, value["manual"], attribution,
                privacy["sec"][4][1],
            )),
            "network FAQ": " ".join((
                network, value["manual"], attribution,
            )),
            "privacy meta": value["summary"],
            "privacy lead": value["summary"],
            "privacy vow": " ".join((
                value["ledger"], network, value["manual"], attribution,
            )),
            "network title": value["networkTitle"],
            "network section": " ".join((network, value["manual"])),
            "ledger section": value["ledger"],
            "rate section": " ".join((
                workflow, network, value["manual"], attribution,
            )),
            "children section": " ".join((
                value["summary"], network, value["manual"],
            )),
            "control section": " ".join((value["delete"], value["manual"])),
            "changes section": value["changes"],
        }
        actual = {
            "foot": entry["foot"],
            "support meta": support["meta"],
            "currency FAQ": support["faq"][1][1],
            "storage FAQ": support["faq"][5][1],
            "network FAQ": support["faq"][7][1],
            "privacy meta": privacy["meta"],
            "privacy lead": privacy["lead"],
            "privacy vow": privacy["vow"],
            "network title": privacy["sec"][1][0],
            "network section": privacy["sec"][1][1],
            "ledger section": privacy["sec"][2][1],
            "rate section": privacy["sec"][3][1],
            "children section": privacy["sec"][6][1],
            "control section": privacy["sec"][7][1],
            "changes section": privacy["sec"][8][1],
        }
        for label, expected_copy in expected.items():
            if actual[label] != expected_copy:
                errors.append(f"{locale}: stale {label}")
    return errors


def load_locales():
    data = {}
    for f in sorted((SRC / "locales").glob("part-*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        for code, value in chunk.items():
            if code in data:
                sys.exit(f"duplicate locale {code} in {f.name}")
            data[code] = value
    missing = [c for c in LOCALES if c not in data]
    extra = [c for c in data if c not in LOCALES]
    if missing:
        sys.exit(f"missing locales: {', '.join(missing)}")
    if extra:
        sys.exit(f"unknown locales: {', '.join(extra)}")
    privacy_errors = privacy_contract_errors(data, load_disclosures())
    if privacy_errors:
        sys.exit("\n".join(privacy_errors))
    return data


def slim(data, page):
    """Keep shared keys plus this page's block, in the shipped locale order."""
    out = {}
    for code in LOCALES:
        src = data[code]
        row = {k: src[k] for k in SHARED}
        row[page] = src[page]
        out[code] = row
    return out


def esc(text):
    return html.escape(text, quote=True)


def fallback(entry, page):
    """Static English markup so the page reads with JavaScript disabled."""
    block = entry[page]
    if page == "s":
        extra = "<ul class=\"chips\">" + "".join(
            f"<li>{esc(c)}</li>" for c in block["chips"]) + "</ul>"
        parts = [f'<h2 class="sect">{esc(block["faqT"])}<span class="rule"></span></h2>',
                 '<div class="faq">']
        for i, (q, a) in enumerate(block["faq"], 1):
            parts.append(
                f'<details class="q" open><summary><span class="n">{i}</span>'
                f'<span>{esc(q)}</span></summary><div class="a">{esc(a)}</div></details>')
        parts.append("</div>")
    else:
        extra = f'<p class="updated">{esc(block["upd"])} {UPDATED}</p>'
        parts = [f'<section class="card vow"><strong>{esc(block["vow"])}</strong></section>']
        for head, text in block["sec"]:
            parts.append(f'<section class="card policy"><h3>{esc(head)}</h3>'
                         f'<p>{esc(text)}</p></section>')
    parts.append(
        '<section class="card contact">'
        f'<h2>{esc(block["cT"])}</h2><p>{esc(block["cL"])}</p>'
        '<a class="btn" href="mailto:hourstag.app@gmail.com">'
        f'{esc(block["cB"])}</a>'
        '<a class="mail" href="mailto:hourstag.app@gmail.com">hourstag.app@gmail.com</a>'
        "</section>")
    return extra, "\n".join(parts)


def build():
    data = load_locales()
    css = (SRC / "style.css").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    tpl = (SRC / "page.tpl.html").read_text(encoding="utf-8")
    base = data["en-US"]

    for page, filename in (("s", "index.html"), ("p", "privacy.html")):
        block = base[page]
        extra, body = fallback(base, page)
        payload = json.dumps(slim(data, page), ensure_ascii=False,
                             separators=(",", ":"))
        # </script> can never appear inside the JSON payload
        payload = payload.replace("</", "<\\/")
        out = (tpl
               .replace("__TITLE__", esc(block["title"]))
               .replace("__DESC__", esc(block["meta"]))
               .replace("__FILE__", "" if filename == "index.html" else filename)
               .replace("__PAGE__", page)
               .replace("__BADGE__", esc(block["eyebrow"]))
               .replace("__H1__", esc(block["h1"]))
               .replace("__LEAD__", esc(block["lead"]))
               .replace("__HERO_EXTRA__", extra)
               .replace("__FALLBACK__", body)
               .replace("__FOOT__", esc(base["foot"]))
               .replace("/*__CSS__*/", css)
               .replace("/*__APP__*/", app)
               .replace("/*__DATA__*/{}", payload))
        (ROOT / filename).write_text(out, encoding="utf-8")
        print(f"built {filename}  {len(out) / 1024:.0f} KB  "
              f"{len(LOCALES)} locales shipped, {len(PENDING)} pending")


if __name__ == "__main__":
    build()
