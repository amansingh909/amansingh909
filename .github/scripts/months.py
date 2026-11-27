#!/usr/bin/env python3
"""Adds month names to the 3D contribution graph, lying flat on the floor along the grid's front edge.

Usage: python3 .github/scripts/months.py profile-3d-contrib/profile-red.svg

The grid math copies the graph tool's (create-3d-contrib.ts in the pinned version): each week moves
width/64 to the right and down at 30 degrees, each weekday moves the same distance to the left. The
date range comes from the "YYYY-MM-DD / YYYY-MM-DD" text the tool prints in the corner, so no token
is needed. Running it twice replaces the labels instead of stacking a second set.
"""
import datetime
import math
import re
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
MARK = "profile-months"
RANGE = re.compile(r">(\d{4}-\d{2}-\d{2}) / (\d{4}-\d{2}-\d{2})<")
FLOOR = "0.866 0.5 -0.866 0.5"   # text x runs along the weeks, text y runs toward the viewer


class Grid:
    def __init__(self, width, height, first, last):
        self.dx = width / 64
        self.dy = self.dx * math.tan(math.radians(30))
        first_dow = (first.weekday() + 1) % 7          # Sunday = 0, like the tool
        weeks = math.ceil(((last - first).days + 1 + first_dow) / 7)
        self.sunday = first - datetime.timedelta(days=first_dow)
        self.ox = self.dx * 7
        self.oy = height - (weeks + 7) * self.dy

    def point(self, week, dow):
        """Screen position of a floor point; week and dow can be fractional."""
        return self.ox + (week - dow) * self.dx, self.oy + (week + dow) * self.dy

    def week_of(self, date):
        return (date - self.sunday).days // 7


def month_weeks(first, last):
    """[(month name, week index)] for every month that starts in the range. The first, partial month
    keeps its name only when the next label is at least 3 weeks later, so the two don't collide."""
    grid = Grid(64, 0, first, last)
    labels = []
    if first.day != 1:
        labels.append((f"{first:%b}", 0))
    d = datetime.date(first.year + first.month // 12, first.month % 12 + 1, 1) if first.day != 1 else first
    while d <= last:
        labels.append((f"{d:%b}", grid.week_of(d)))
        d = datetime.date(d.year + d.month // 12, d.month % 12 + 1, 1)
    if first.day != 1 and len(labels) > 1 and labels[1][1] - labels[0][1] < 3:
        labels.pop(0)
    return labels


def add_months(svg_text):
    if "<!DOCTYPE" in svg_text or "<!ENTITY" in svg_text:
        raise ValueError("unexpected DOCTYPE/ENTITY in the graph")
    m = RANGE.search(svg_text)
    if not m:
        raise ValueError("no 'YYYY-MM-DD / YYYY-MM-DD' date range found in the graph")
    first, last = (datetime.date.fromisoformat(s) for s in m.groups())
    ET.register_namespace("", SVG)
    root = ET.fromstring(svg_text)
    for el in [el for el in root if el.get("class") == MARK]:
        root.remove(el)
    grid = Grid(float(root.get("width")), float(root.get("height")), first, last)
    g = ET.SubElement(root, f"{{{SVG}}}g", {"class": MARK})
    for name, week in month_weeks(first, last):
        x, y = grid.point(week + 0.15, 7.0)
        t = ET.SubElement(g, f"{{{SVG}}}text", {"transform": f"matrix({FLOOR} {x:.2f} {y:.2f})",
                                                 "class": "fill-weak", "style": "font-size: 18px;"})
        t.text = name
    return ET.tostring(root, encoding="unicode")


def main(argv):
    path = argv[0]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(add_months(text))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
