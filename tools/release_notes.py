#!/usr/bin/env python3
"""Печатает описание релиза из CHANGELOG.md для тега (аргумент без 'v').

Использование: python tools/release_notes.py <тег>   # например v0.1.3
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

FALLBACK = "Сборка Windows-версии GUI. Подробности в CHANGELOG.md"


def main():
    tag = (sys.argv[1] if len(sys.argv) > 1 else "").lstrip("v")
    if not tag or not CHANGELOG.exists():
        print(FALLBACK)
        return
    text = CHANGELOG.read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(tag)}\](.*?)(?=^## )", text, re.S | re.M)
    body = ""
    if m:
        lines = [ln for ln in m.group(1).splitlines() if ln.strip()]
        while lines and not lines[0].startswith("###"):
            lines.pop(0)  # строка даты "— YYYY-MM-DD"
        body = "\n".join(lines).strip()
    print(body or FALLBACK)


if __name__ == "__main__":
    main()
