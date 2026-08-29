#!/usr/bin/env python3
"""Build the MoneyTag support site.

Merges src/locales/*.json into two fully self-contained pages:
  index.html   -> support + FAQ
  privacy.html -> privacy policy

Each page carries inline CSS, inline JS and only the locale strings that page
needs. No external requests of any kind are emitted.
"""
import html
import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DISCLOSURES = SRC / "privacy_disclosures.json"
BUILD_RECEIPT = ROOT / "surface-build.json"
GENERATED_CSS = ROOT / "surface-generated.css"
CROSSPROMO = SRC / "crosspromo.html"
TEMPLATE_MARKER = "<!-- required-surface-template -->"

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
SITE = "https://alice51849.github.io/moneytag-support/"
APP_STORE_URL = "https://apps.apple.com/app/id6801956402"
UPDATED = "2026-08-17"
SHARED = ("n", "l", "tag", "nav", "lang", "foot")
DISCLOSURE_KEYS = (
    "summary", "ledger", "request", "processing", "use", "manual",
    "attribution", "networkTitle", "delete", "changes",
)


X_DEFAULT_TARGETS = {'index': '', 'support': '', 'privacy': 'privacy.html'}


def x_default_url(surface):
    """Root-level English equivalent of a surface, per upstream convention."""
    return SITE.rstrip("/") + "/" + X_DEFAULT_TARGETS.get(surface, "")


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
    for code in LOCALES:
        surface = data[code].get("surface", {})
        if set(surface) != {"appStore", "moreApps"} or not all(surface.values()):
            sys.exit(f"{code}: incomplete required-surface labels")
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


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def route_path(locale, surface):
    name = "index.html" if surface == "index" else f"{surface}.html"
    return ROOT / locale / name


def canonical_url(locale, surface):
    suffix = "" if surface == "index" else f"{surface}.html"
    return f"{SITE}{locale}/{suffix}"


def og_locale(locale):
    explicit = {
        "zh-Hans": "zh_CN", "zh-Hant": "zh_TW", "ca": "ca_ES",
        "hr": "hr_HR", "cs": "cs_CZ", "da": "da_DK", "fi": "fi_FI",
        "el": "el_GR", "he": "he_IL", "hi": "hi_IN", "hu": "hu_HU",
        "id": "id_ID", "it": "it_IT", "ja": "ja_JP", "ko": "ko_KR",
        "ms": "ms_MY", "no": "nb_NO", "pl": "pl_PL", "ro": "ro_RO",
        "ru": "ru_RU", "sk": "sk_SK", "sv": "sv_SE", "th": "th_TH",
        "tr": "tr_TR", "uk": "uk_UA", "vi": "vi_VN",
    }
    if locale in explicit:
        return explicit[locale]
    parts = locale.split("-", 1)
    return parts[0] if len(parts) == 1 else f"{parts[0]}_{parts[1].upper()}"


def alternates(surface):
    rows = [
        '<link rel="alternate" hreflang="{}" href="{}">'.format(
            esc(locale), esc(canonical_url(locale, surface))
        )
        for locale in LOCALES
    ]
    rows.append(
        '<link rel="alternate" hreflang="x-default" href="{}">'.format(
            esc(x_default_url(surface))
        )
    )
    return "\n".join(rows)


def language_links(data, surface, current):
    rows = []
    for locale in LOCALES:
        current_attr = ' aria-current="page"' if locale == current else ""
        rows.append(
            '<a hreflang="{}" lang="{}" href="{}"{}>{}</a>'.format(
                esc(locale),
                esc(locale),
                esc(canonical_url(locale, surface)),
                current_attr,
                esc(data[locale]["n"]),
            )
        )
    return "\n".join(rows)


def load_crosspromo():
    source = CROSSPROMO.read_text(encoding="utf-8")
    apps = []
    for match in re.finditer(
        r'<a href="(https://apps\.apple\.com/[^"]+)"[^>]*>(.*?)</a>',
        source,
        re.S,
    ):
        name = re.search(r"<strong[^>]*>(.*?)</strong>", match.group(2), re.S)
        if name:
            apps.append({
                "name": html.unescape(re.sub(r"<[^>]+>", "", name.group(1))).strip(),
                "url": html.unescape(match.group(1)),
            })
    if len(apps) != 4 or len({app["url"] for app in apps}) != 4:
        sys.exit("src/crosspromo.html must retain four unique remote App Store links")
    return source, apps


def surface_content(entry, surface):
    if surface == "privacy":
        block = entry["p"]
        return {
            "title": block["title"],
            "description": block["meta"],
            "eyebrow": block["eyebrow"],
            "heading": block["h1"],
            "lead": block["lead"],
            "sections": block["sec"],
            "contactTitle": block["cT"],
            "contact": block["cL"],
            "contactButton": block["cB"],
        }
    block = entry["s"]
    sections = block["faq"]
    if surface == "index":
        sections = [
            [block["faqT"], " · ".join(block["chips"])],
            *block["faq"][:3],
        ]
    return {
        "title": block["title"],
        "description": block["meta"],
        "eyebrow": block["eyebrow"],
        "heading": block["h1"],
        "lead": block["lead"],
        "sections": sections,
        "contactTitle": block["cT"],
        "contact": block["cL"],
        "contactButton": block["cB"],
    }


def normalize_description(value):
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= 180:
        return value
    prefix = value[:180]
    cut = max(prefix.rfind(mark) + 1 for mark in ".!?。！？")
    if cut < 100:
        cut = prefix.rfind(" ")
    if cut < 100:
        cut = 180
    return prefix[:cut].rstrip(" ,;:，；：")


def schema_payload(locale, surface, content, canonical):
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage" if surface == "support" else "WebPage",
        "name": content["title"],
        "description": content["description"],
        "inLanguage": locale,
        "url": canonical,
        "isPartOf": {
            "@type": "WebSite",
            "name": "MoneyTag",
            "url": SITE,
        },
        "about": {
            "@type": "MobileApplication",
            "name": "MoneyTag",
            "operatingSystem": "iOS",
            "sameAs": APP_STORE_URL,
        },
    }
    if surface == "support":
        payload["mainEntity"] = [
            {
                "@type": "Question",
                "name": heading,
                "acceptedAnswer": {"@type": "Answer", "text": body},
            }
            for heading, body in content["sections"]
        ]
    return payload


def surface_crosspromo(entry, apps):
    heading = entry["surface"]["moreApps"]
    links = "\n".join(
        '<a class="surface-mail" href="{}" rel="noopener">{}</a>'.format(
            esc(app["url"]), esc(app["name"])
        )
        for app in apps
    )
    return (
        '<section class="surface-card surface-contact" '
        'data-surface-crosspromo="true" '
        f'aria-label="{esc(heading)}"><h2>{esc(heading)}</h2>'
        f"{links}</section>"
    )


def render_surface(data, template, locale, surface, apps):
    entry = data[locale]
    content = surface_content(entry, surface)
    content["description"] = normalize_description(content["description"])
    canonical = canonical_url(locale, surface)
    nav = "".join(
        (
            f'<a href="{esc(canonical_url(locale, "index"))}">MoneyTag</a>',
            f'<a href="{esc(canonical_url(locale, "support"))}">'
            f'{esc(entry["nav"][0])}</a>',
            f'<a href="{esc(canonical_url(locale, "privacy"))}">'
            f'{esc(entry["nav"][1])}</a>',
        )
    )
    sections = "".join(
        '<section class="surface-card"><h2>{}</h2><p>{}</p></section>'.format(
            esc(heading), esc(body)
        )
        for heading, body in content["sections"]
    )
    subject = quote("MoneyTag support")
    contact = (
        '<section class="surface-card surface-contact">'
        f'<h2>{esc(content["contactTitle"])}</h2>'
        f'<p>{esc(content["contact"])}</p>'
        f'<a class="surface-mail" aria-label="{esc(content["contactButton"])}" '
        f'href="mailto:hourstag.app@gmail.com?subject={subject}">'
        "hourstag.app@gmail.com</a>"
        '<a class="surface-button" data-surface-own-app="true" '
        f'href="{APP_STORE_URL}" rel="noopener">'
        f'{esc(entry["surface"]["appStore"])}</a></section>'
    )
    schema = json.dumps(
        schema_payload(locale, surface, content, canonical),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    values = {
        "__LOCALE__": esc(locale),
        "__DIR__": "rtl" if locale in RTL else "ltr",
        "__SURFACE_TITLE__": esc(content["title"]),
        "__SURFACE_DESCRIPTION__": esc(content["description"]),
        "__CANONICAL__": esc(canonical),
        "__ALTERNATES__": alternates(surface),
        "__OG_LOCALE__": esc(og_locale(locale)),
        "__SCHEMA__": schema,
        "__HOME_URL__": esc(canonical_url(locale, "index")),
        "__NAV_LABEL__": "MoneyTag",
        "__NAV__": nav,
        "__EYEBROW__": esc(content["eyebrow"]),
        "__HEADING__": esc(content["heading"]),
        "__LEAD__": esc(content["lead"]),
        "__SECTIONS__": sections,
        "__CONTACT__": contact,
        "__SURFACE_CROSSPROMO__": surface_crosspromo(entry, apps),
        "__LANGUAGE__": esc(entry["lang"]),
        "__LOCALE_NAME__": esc(entry["n"]),
        "__LANGUAGE_LINKS__": language_links(data, surface, locale),
    }
    output = template
    for key, value in values.items():
        output = output.replace(key, value)
    unresolved = re.findall(r"__[A-Z][A-Z_]+__", output)
    if unresolved:
        sys.exit(f"{locale}/{surface}: unresolved template fields {unresolved}")
    return output


def write_surface_css():
    GENERATED_CSS.write_text(
        """*{box-sizing:border-box}html{color-scheme:light dark}body{margin:0;min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",sans-serif;line-height:1.65;color:#29261f;background:radial-gradient(circle at 12% 0,#C9A22724,transparent 34rem),radial-gradient(circle at 90% 8%,#1F9D6320,transparent 32rem),#fbf8f0}a{color:#1F7D54}.surface-header,.surface-header nav,.surface-contact,.surface-languages nav{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.surface-header{max-width:1040px;margin:auto;padding:22px 20px;justify-content:space-between}.surface-brand{font-size:1.05rem;font-weight:750;text-decoration:none;color:inherit}.surface-header nav a{padding:8px 10px;text-decoration:none}main,.surface-languages,footer{width:min(920px,calc(100% - 32px));margin:auto}.surface-hero{padding:44px 0 24px}.surface-eyebrow{font-size:.8rem;letter-spacing:.08em;text-transform:uppercase;color:#1F7D54;font-weight:700}h1{font-size:clamp(2rem,7vw,4.2rem);line-height:1.05;letter-spacing:-.035em;margin:.25em 0}h2{font-size:1.2rem;margin-top:0}.surface-card{padding:22px;margin:14px 0;border:1px solid #1F9D6330;border-radius:22px;background:rgba(255,255,255,.78);box-shadow:0 20px 60px #C9A22712}.surface-contact{align-items:flex-start;flex-direction:column}.surface-mail,.surface-button{display:inline-flex;min-height:44px;align-items:center;padding:10px 16px;border-radius:14px;text-decoration:none;font-weight:700}.surface-mail{border:1px solid #1F9D6355}.surface-button{color:white;background:linear-gradient(135deg,#1F9D63,#C9A227)}.surface-languages{margin-top:28px;padding:16px;border:1px solid #1F9D6330;border-radius:18px}.surface-languages summary{cursor:pointer;font-weight:700}.surface-languages nav{padding-top:12px;align-items:stretch}.surface-languages nav a{padding:7px 10px;border-radius:9px;text-decoration:none;background:#1F9D630d}footer{padding:30px 0 44px;opacity:.65}[dir=rtl] .surface-header,[dir=rtl] .surface-contact{text-align:right}@media(prefers-color-scheme:dark){body{color:#fff9e8;background:radial-gradient(circle at 12% 0,#C9A22738,transparent 34rem),radial-gradient(circle at 90% 8%,#1F9D6328,transparent 32rem),#151210}.surface-card{background:rgba(34,30,23,.86)}}""",
        encoding="utf-8",
    )


def update_sitemap():
    path = ROOT / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    start = "<!-- required-surfaces:start -->"
    end = "<!-- required-surfaces:end -->"
    if (start in text) != (end in text):
        sys.exit("sitemap.xml has an incomplete required-surfaces block")
    urls = [
        canonical_url(locale, surface)
        for locale in LOCALES
        for surface in ("index", "support", "privacy")
    ]
    rows = "\n".join(
        f"  <url><loc>{esc(url)}</loc></url>" for url in sorted(urls)
    )
    managed = f"  {start}\n{rows}\n  {end}"
    if start in text:
        text = re.sub(
            rf"(?m)^  {re.escape(start)}\n.*?^  {re.escape(end)}$",
            managed,
            text,
            count=1,
            flags=re.S,
        )
    else:
        text = re.sub(
            r"(?m)^</urlset>$",
            managed + "\n</urlset>",
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")


def build_required_surfaces(data, template, apps):
    write_surface_css()
    outputs = []
    for locale in LOCALES:
        for surface in ("index", "support", "privacy"):
            path = route_path(locale, surface)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                render_surface(data, template, locale, surface, apps),
                encoding="utf-8",
            )
            outputs.append(path)
    update_sitemap()
    outputs.extend((GENERATED_CSS, ROOT / "sitemap.xml"))
    records = {
        str(path.relative_to(ROOT)): file_sha(path)
        for path in sorted(outputs, key=lambda item: str(item.relative_to(ROOT)))
    }
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = {
        "schema": "support-required-surfaces-build/v1",
        "site": "moneytag-support",
        "officialLocaleCount": 50,
        "requiredSurfaceCount": 150,
        "contentDigest": digest,
        "files": records,
    }
    BUILD_RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"built 150 required locale surfaces  {digest}")


def build():
    data = load_locales()
    css = (SRC / "style.css").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    template_source = (SRC / "page.tpl.html").read_text(encoding="utf-8")
    if template_source.count(TEMPLATE_MARKER) != 1:
        sys.exit("src/page.tpl.html must contain one required-surface template")
    tpl, surface_tpl = template_source.split(TEMPLATE_MARKER, 1)
    surface_tpl = surface_tpl.lstrip("\n")
    crosspromo_html, crosspromo_apps = load_crosspromo()
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
               .replace("__CROSSPROMO__", crosspromo_html)
               .replace("/*__CSS__*/", css)
               .replace("/*__APP__*/", app)
               .replace("/*__DATA__*/{}", payload))
        (ROOT / filename).write_text(out, encoding="utf-8")
        print(f"built {filename}  {len(out) / 1024:.0f} KB  "
              f"{len(LOCALES)} locales shipped, {len(PENDING)} pending")
    build_required_surfaces(data, surface_tpl, crosspromo_apps)


if __name__ == "__main__":
    build()
