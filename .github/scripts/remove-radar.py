#!/usr/bin/env python3
"""Removes the radar chart from the 3D contribution graph, keeping the bars, the language pie and the totals.

Usage: python3 .github/scripts/remove-radar.py profile-3d-contrib/profile-red.svg

The radar chart is the top-level group whose axis labels are Commit, Issue, PullReq, Review and Repo.
Exits with an error (and leaves the file alone) if it cannot find exactly one such group, so a
changed layout fails the workflow run instead of committing a broken graph.
"""
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
RADAR_LABELS = {"Commit", "Issue", "PullReq", "Review", "Repo"}


def is_radar(group):
    labels = {(t.text or "").strip() for t in group.iter(f"{{{SVG}}}text")}
    return RADAR_LABELS <= labels


def main(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        sys.exit(f"{path}: unexpected DOCTYPE/ENTITY, refusing to parse")
    ET.register_namespace("", SVG)
    root = ET.fromstring(text)
    radars = [g for g in root if g.tag == f"{{{SVG}}}g" and is_radar(g)]
    if len(radars) != 1:
        sys.exit(f"{path}: expected one radar chart group, found {len(radars)}")
    root.remove(radars[0])
    with open(path, "w", encoding="utf-8") as f:
        f.write(ET.tostring(root, encoding="unicode"))


if __name__ == "__main__":
    main(sys.argv[1])
