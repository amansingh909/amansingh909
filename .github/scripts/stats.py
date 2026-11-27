#!/usr/bin/env python3
"""Adds three numbers to the empty top-right corner of the 3D contribution graph:
busiest day, longest streak and current streak, from the owner's contribution calendar
(private contributions included).

Usage: LANGS_TOKEN=... python3 .github/scripts/stats.py profile-3d-contrib/profile-red.svg

Uses the same read-only LANGS_TOKEN as languages.py. Without it the script leaves the graph alone
and exits 0. Running it twice replaces the numbers instead of stacking a second copy.
"""
import datetime
import os
import sys
import xml.etree.ElementTree as ET

from languages import graphql

SVG = "http://www.w3.org/2000/svg"
MARK = "profile-stats"

CALENDAR = """
query { viewer { contributionsCollection { contributionCalendar {
  weeks { contributionDays { date contributionCount } }
} } } }
"""


def calendar(token):
    weeks = graphql(token, CALENDAR)["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def _label(date):
    d = datetime.date.fromisoformat(date)
    return f"{d:%b} {d.day}"


def days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def compute(cal):
    """cal: [(YYYY-MM-DD, count)] oldest first, ending today. Today at 0 doesn't break the streak yet."""
    best_date, best = max(cal, key=lambda dc: dc[1])
    longest, frm, to, run, start = 0, None, None, 0, None
    for date, n in cal:
        if n > 0:
            start = date if run == 0 else start
            run += 1
            if run > longest:
                longest, frm, to = run, start, date
        else:
            run = 0
    i = len(cal) - 1
    if cal[i][1] == 0:
        i -= 1
    current = 0
    while i >= 0 and cal[i][1] > 0:
        current += 1
        i -= 1
    return {"best": best, "best_date": _label(best_date), "longest": longest,
            "longest_from": _label(frm) if frm else None, "longest_to": _label(to) if to else None,
            "current": current}


def stats_group(st):
    rows = [(str(st["best"]), f"busiest day · {st['best_date']}")]
    streak = "longest streak" + (f" · {st['longest_from']} to {st['longest_to']}" if st["longest"] else "")
    rows.append((days(st["longest"]), streak))
    rows.append((days(st["current"]), "current streak"))
    g = ET.Element(f"{{{SVG}}}g", {"transform": "translate(1240, 0)", "class": MARK})
    for i, (number, label) in enumerate(rows):
        y = 125 + i * 95
        num = ET.SubElement(g, f"{{{SVG}}}text", {"x": "0", "y": str(y), "text-anchor": "end", "class": "fill-strong",
                                                  "style": "font-size: 44px; font-weight: bold;"})
        num.text = number
        lab = ET.SubElement(g, f"{{{SVG}}}text", {"x": "0", "y": str(y + 30), "text-anchor": "end", "class": "fill-weak",
                                                  "style": "font-size: 20px;"})
        lab.text = label
    return g


def add_stats(svg_text, st):
    if "<!DOCTYPE" in svg_text or "<!ENTITY" in svg_text:
        raise ValueError("unexpected DOCTYPE/ENTITY in the graph")
    ET.register_namespace("", SVG)
    root = ET.fromstring(svg_text)
    for el in [el for el in root if el.get("class") == MARK]:
        root.remove(el)
    root.append(stats_group(st))
    return ET.tostring(root, encoding="unicode")


def main(argv):
    path = argv[0]
    token = os.environ.get("LANGS_TOKEN")
    if not token:
        print("LANGS_TOKEN is not set; leaving the graph without the corner stats.", file=sys.stderr)
        return 0
    st = compute(calendar(token))
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(add_stats(text, st))
    print(f"Stats: busiest {st['best']} on {st['best_date']}, longest {days(st['longest'])}, current {days(st['current'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
