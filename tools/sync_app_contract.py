#!/usr/bin/env python3
"""Synchronize localized support copy with MoneyTag's shipped free/export rules."""

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = ROOT.parent / "46_MoneyTag"
LOCALE_ROOT = ROOT / "src" / "locales"
UI = json.loads((APP_ROOT / "assets" / "ui_i18n.json").read_text(encoding="utf-8"))


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
    changed = 0
    locales = 0
    for path in sorted(LOCALE_ROOT.glob("part-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        for locale, copy in data.items():
            locales += 1
            ui = UI[language_group(locale)]
            free = ui["freeStatus"].replace("{p}", "1").replace("{n}", "5")
            free_answer = " ".join(
                (
                    sentence(free),
                    sentence(ui["unlockSubtitle"]),
                    sentence(
                        " · ".join(
                            (ui["exportCsv"], ui["exportPdf"], ui["backupRestore"])
                        )
                    ),
                )
            )
            export_answer = " ".join(
                (
                    sentence(
                        " · ".join(
                            (ui["exportCsv"], ui["exportPdf"], ui["backupRestore"])
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
    print(f"Synchronized {locales} locales across {changed} changed files")


if __name__ == "__main__":
    main()
