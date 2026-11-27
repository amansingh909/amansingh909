#!/usr/bin/env python3
"""Builds a tall version of the 3D contribution graph for phones held upright.

Usage: python3 .github/scripts/portrait.py profile-3d-contrib/profile-red.svg profile-3d-contrib/profile-red-portrait.svg

The wide graph (1280 x 850) shrinks to about a quarter on a phone, so its text gets tiny. This stacks the
same parts in a 720-wide column instead: the 3D grid with its month labels, then the three stats side by
side, then the language pie (scaled up), then the totals. The README shows it through a <picture> source
with media="(max-width: 600px)", so desktops and phones held sideways keep the wide one.
"""
import copy
import sys
import xml.etree.ElementTree as ET

from stats import glyph_text

SVG = "http://www.w3.org/2000/svg"
W, WIDE_W, WIDE_H = 720, 1280, 850
S = W / WIDE_W          # the grid keeps its full width
TOP = 40                # empty band above the grid in the wide version
PIE_SCALE, TOTALS_SCALE = 1.2, 1.15
PIE_W = 470             # donut plus legend, in the pie group's own units


def tag(el):
    return el.tag.split("}")[-1]


def find_parts(root):
    parts = {"style": None, "bars": None, "pie": None, "totals": None, "months": None, "stats": None}
    for el in root:
        t, cls = tag(el), el.get("class")
        if t == "style":
            parts["style"] = el
        elif t != "g":
            continue
        elif cls == "profile-months":
            parts["months"] = el
        elif cls == "profile-stats":
            parts["stats"] = el
        elif el.get("transform") == "translate(40, 520)":
            parts["pie"] = el
        elif any((x.text or "").strip() == "contributions" for x in el.iter(f"{{{SVG}}}text")):
            parts["totals"] = el
        elif parts["bars"] is None:
            parts["bars"] = el
    return parts


def build(svg_text):
    if "<!DOCTYPE" in svg_text or "<!ENTITY" in svg_text:
        raise ValueError("unexpected DOCTYPE/ENTITY in the graph")
    ET.register_namespace("", SVG)
    parts = find_parts(ET.fromstring(svg_text))
    if parts["bars"] is None or parts["totals"] is None:
        raise ValueError("the wide graph is missing its grid or totals")
    body = []

    # 1. the 3D grid and month labels, full width
    grid = ET.Element(f"{{{SVG}}}g", {"transform": f"translate(0 {-TOP * S:.2f}) scale({S:.4f})"})
    grid.append(copy.deepcopy(parts["bars"]))
    if parts["months"] is not None:
        months = copy.deepcopy(parts["months"])
        for t in months:                                   # bigger labels so they read at phone size
            t.set("style", "font-size: 30px;")
        grid.append(months)
    body.append(grid)
    y = (WIDE_H - TOP) * S

    totals = copy.deepcopy(parts["totals"])
    for el in list(totals):
        if el.get("dominant-baseline") == "hanging":      # the date range goes in the top corner
            date = ET.Element(f"{{{SVG}}}text", {"x": str(W - 16), "y": "14", "dominant-baseline": "hanging",
                                                  "text-anchor": "end", "class": "fill-weak",
                                                  "style": "font-size: 15px;"})
            date.text = el.text
            body.append(date)
            totals.remove(el)

    # 2. the three stats side by side, numbers on top, labels underneath
    if parts["stats"] is not None:
        kids = list(parts["stats"])
        numbers = [k.get("aria-label") for k in kids if k.get("class") == "stat-number"]
        labels = [k.text or "" for k in kids if tag(k) == "text"]
        base = y + 58
        lines_max = 1
        stats = ET.Element(f"{{{SVG}}}g", {"class": "profile-stats"})
        for i, (number, label) in enumerate(zip(numbers, labels)):
            cx = W / 6 + i * W / 3
            stats.append(glyph_text(number, 44, cx, base, "middle", "fill-strong"))
            lines = label.split(" · ")
            lines_max = max(lines_max, len(lines))
            for j, line in enumerate(lines):
                t = ET.SubElement(stats, f"{{{SVG}}}text", {"x": f"{cx:.1f}", "y": f"{base + 30 + j * 25:.1f}",
                                                             "text-anchor": "middle", "class": "fill-weak",
                                                             "style": "font-size: 21px;"})
                t.text = line
        body.append(stats)
        y = base + 30 + (lines_max - 1) * 25 + 12

    # 3. the language pie, a bit bigger and centred
    if parts["pie"] is not None:
        pie = copy.deepcopy(parts["pie"])
        pie.set("transform", f"translate({(W - PIE_W * PIE_SCALE) / 2:.1f} {y + 24:.1f}) scale({PIE_SCALE})")
        body.append(pie)
        y += 24 + 260 * PIE_SCALE

    # 4. contributions, stars and forks, centred under everything
    top = y + 20
    span_left, span_right, span_top, span_bottom = 300, 795, 795, 842
    k = TOTALS_SCALE
    totals.set("transform", f"translate({W / 2 - (span_left + span_right) / 2 * k:.1f} {top - span_top * k:.1f}) scale({k})")
    body.append(totals)
    height = top + (span_bottom - span_top) * k + 16

    root = ET.Element(f"{{{SVG}}}svg", {"width": str(W), "height": f"{height:.0f}",
                                         "viewBox": f"0 0 {W} {height:.0f}"})
    if parts["style"] is not None:
        root.append(copy.deepcopy(parts["style"]))
    ET.SubElement(root, f"{{{SVG}}}rect", {"x": "0", "y": "0", "width": str(W), "height": f"{height:.0f}",
                                            "class": "fill-bg"})
    for el in body:
        root.append(el)
    return ET.tostring(root, encoding="unicode")


def main(argv):
    src, dst = argv
    with open(src, encoding="utf-8") as f:
        text = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(build(text))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
