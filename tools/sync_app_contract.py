#!/usr/bin/env python3
"""Synchronize localized App and support copy with MoneyTag's shipped contract."""

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = ROOT.parent / "46_MoneyTag"
LOCALE_ROOT = ROOT / "src" / "locales"
DISCLOSURES = ROOT / "src" / "privacy_disclosures.json"
UI = json.loads((APP_ROOT / "assets" / "ui_i18n.json").read_text(encoding="utf-8"))
ORIGINAL_UI = json.loads(json.dumps(UI))
PRIVACY_UI_KEYS = {
    "privacyNote": "ledger",
    "onboardFootnote": "summary",
    "privacyRequestNote": "request",
    "privacyNetworkNote": "processing",
    "privacyUseNote": "use",
    "privacyManualNote": "manual",
    "rateAttribution": "attribution",
}
LEGACY_ATTRIBUTIONS = {
    "en": "Reference rates derived from European Central Bank data via Frankfurter; for informational use.",
    "fr": "Taux de référence issus des données de la Banque centrale européenne via Frankfurter, à titre informatif uniquement.",
    "es": "Tipos de referencia derivados de datos del Banco Central Europeo mediante Frankfurter; solo con fines informativos.",
    "pt": "Taxas de referência derivadas de dados do Banco Central Europeu através do Frankfurter; apenas para fins informativos.",
}


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
        "zh-Hans": "zh-Hans",
        "zh-Hant": "zh-Hant",
        "de-DE": "de",
        "nl-NL": "nl",
        "bn-BD": "bn",
        "gu-IN": "gu",
        "kn-IN": "kn",
        "ml-IN": "ml",
        "mr-IN": "mr",
        "or-IN": "or",
        "pa-IN": "pa",
        "sl-SI": "sl",
        "ta-IN": "ta",
        "te-IN": "te",
        "ur-PK": "ur",
    }
    return exact.get(locale, locale.split("-", 1)[0])


def sentence(value):
    return value.strip().rstrip(".。!?！？") + "."


def main():
    disclosure_payload = json.loads(DISCLOSURES.read_text(encoding="utf-8"))
    disclosure_keys = disclosure_payload["keys"]
    disclosure_groups = {
        group: dict(zip(disclosure_keys, values))
        for group, values in disclosure_payload["groups"].items()
    }
    locale_groups = disclosure_payload["localeGroups"]
    changed = 0
    locales = 0
    ui_changed = False
    for path in sorted(LOCALE_ROOT.glob("part-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        for locale, copy in data.items():
            locales += 1
            app_group = language_group(locale)
            ui = UI[app_group]
            disclosure = disclosure_groups[locale_groups[locale]]
            old_attribution = ORIGINAL_UI[app_group]["rateAttribution"]
            for ui_key, disclosure_key in PRIVACY_UI_KEYS.items():
                value = disclosure[disclosure_key]
                if ui.get(ui_key) != value:
                    ui[ui_key] = value
                    ui_changed = True

            support = copy["s"]
            privacy = copy["p"]
            workflow = support["faq"][1][1]
            for attribution in (
                disclosure["attribution"],
                old_attribution,
                LEGACY_ATTRIBUTIONS.get(app_group),
            ):
                if not attribution:
                    continue
                if workflow.endswith(attribution):
                    workflow = workflow[:-len(attribution)].rstrip()
            stale_ledger = disclosure["ledger"].replace(
                "Frankfurter / ExchangeRate-API", "Frankfurter"
            )
            network = " ".join(
                (
                    disclosure["request"],
                    disclosure["processing"],
                    disclosure["use"],
                )
            )
            expected_privacy = {
                "foot": disclosure["summary"],
                "support_meta": disclosure["summary"],
                "currency_faq": " ".join(
                    (workflow, disclosure["attribution"])
                ),
                "storage_faq": " ".join(
                    (
                        disclosure["ledger"],
                        network,
                        disclosure["manual"],
                        disclosure["attribution"],
                        privacy["sec"][4][1],
                    )
                ),
                "network_faq": " ".join(
                    (network, disclosure["manual"], disclosure["attribution"])
                ),
                "privacy_meta": disclosure["summary"],
                "privacy_lead": disclosure["summary"],
                "privacy_vow": " ".join(
                    (
                        disclosure["ledger"],
                        network,
                        disclosure["manual"],
                        disclosure["attribution"],
                    )
                ),
                "network_title": disclosure["networkTitle"],
                "network_section": " ".join(
                    (network, disclosure["manual"])
                ),
                "ledger_section": disclosure["ledger"],
                "rate_section": " ".join(
                    (
                        workflow,
                        network,
                        disclosure["manual"],
                        disclosure["attribution"],
                    )
                ),
                "children_section": " ".join(
                    (disclosure["summary"], network, disclosure["manual"])
                ),
                "control_section": " ".join(
                    (disclosure["delete"], disclosure["manual"])
                ),
                "changes_section": disclosure["changes"],
            }
            targets = (
                (copy, "foot", expected_privacy["foot"]),
                (support, "meta", expected_privacy["support_meta"]),
                (support["faq"][1], 1, expected_privacy["currency_faq"]),
                (support["faq"][5], 1, expected_privacy["storage_faq"]),
                (support["faq"][7], 1, expected_privacy["network_faq"]),
                (privacy, "meta", expected_privacy["privacy_meta"]),
                (privacy, "lead", expected_privacy["privacy_lead"]),
                (privacy, "vow", expected_privacy["privacy_vow"]),
                (privacy["sec"][1], 0, expected_privacy["network_title"]),
                (privacy["sec"][1], 1, expected_privacy["network_section"]),
                (privacy["sec"][2], 1, expected_privacy["ledger_section"]),
                (privacy["sec"][3], 1, expected_privacy["rate_section"]),
                (privacy["sec"][6], 1, expected_privacy["children_section"]),
                (privacy["sec"][7], 1, expected_privacy["control_section"]),
                (privacy["sec"][8], 1, expected_privacy["changes_section"]),
            )
            for target, key, value in targets:
                if target[key] != value:
                    target[key] = value
                    dirty = True
            if stale_ledger in support["faq"][6][1]:
                support["faq"][6][1] = support["faq"][6][1].replace(
                    stale_ledger, disclosure["ledger"]
                )
                dirty = True

            free = ui["freeStatus"].replace("{p}", "1").replace("{n}", "5")
            free_answer = " ".join(
                (
                    sentence(free),
                    sentence(ui["unlockSubtitle"]),
                    sentence(
                        " · ".join(
                            (
                                ui["exportCsv"],
                                ui["exportPdf"],
                                ui["exportPhoto"],
                                ui["backupRestore"],
                            )
                        )
                    ),
                )
            )
            export_answer = " ".join(
                (
                    sentence(
                        " · ".join(
                            (
                                ui["exportCsv"],
                                ui["exportPdf"],
                                ui["exportPhoto"],
                                ui["backupRestore"],
                            )
                        )
                    ),
                    sentence(ui["backupHint"]),
                )
            )
            faq = copy["s"]["faq"]
            if faq[3][1] != free_answer:
                faq[3][1] = free_answer
                dirty = True
            if faq[8][1] != export_answer:
                faq[8][1] = export_answer
                dirty = True
        if dirty:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed += 1
    if ui_changed:
        (APP_ROOT / "assets" / "ui_i18n.json").write_text(
            json.dumps(UI, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"Synchronized {locales} locales across {changed} changed files; "
        f"App UI changed={ui_changed}"
    )


if __name__ == "__main__":
    main()
