#!/usr/bin/env python3
"""Redraws the language pie in the 3D contribution graph so it counts private repos too.

Usage: LANGS_TOKEN=... python3 .github/scripts/languages.py profile-3d-contrib/profile-red.svg

It counts the owner's commits from the last 365 days on the default branch of every repo they own
(private repos and forks included), groups them by each repo's main language, and swaps the graph
tool's public-only pie for a neon one built from those counts. Only language names and percentages
end up in the image, never repo names.

LANGS_TOKEN is a fine-grained token with read-only Contents access to the owner's repos. Without it
the script leaves the graph alone and exits 0, so the tool's own pie stays.
"""
import datetime
import json
import math
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
PIE_TRANSFORM = "translate(40, 520)"   # where the graph tool puts its pie (fixed by the pinned version)
OTHER_COLOR = "#444444"
TOP = 5
# cyberpunk neon, handed out by rank; "Other" gets a dim slate
NEON = ["#ff2a6d", "#05d9e8", "#fcee0a", "#b026ff", "#39ff14"]
OTHER_NEON = "#3a3f58"

QUERY = """
query($uid: ID!, $since: GitTimestamp!, $cursor: String) {
  viewer {
    repositories(first: 100, ownerAffiliations: OWNER, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        primaryLanguage { name color }
        defaultBranchRef { target { ... on Commit { history(since: $since, author: {id: $uid}) { totalCount } } } }
      }
    }
  }
}
"""


def graphql(token, query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-languages"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(f"GitHub API error: {body['errors'][0].get('message')}")
    return body["data"]


def fetch(token):
    """[(language, color, commits)] for every owned repo that has a main language."""
    uid = graphql(token, "query { viewer { id } }")["viewer"]["id"]
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, cursor = [], None
    while True:
        repos = graphql(token, QUERY, {"uid": uid, "since": since, "cursor": cursor})["viewer"]["repositories"]
        for node in repos["nodes"]:
            lang = node.get("primaryLanguage")
            target = (node.get("defaultBranchRef") or {}).get("target") or {}
            count = (target.get("history") or {}).get("totalCount", 0)
            if lang:
                rows.append((lang["name"], lang.get("color") or OTHER_COLOR, count))
        if not repos["pageInfo"]["hasNextPage"]:
            return rows
        cursor = repos["pageInfo"]["endCursor"]


def aggregate(rows, top=TOP):
    """Sum commits per language, drop zeros, keep the top languages and fold the rest into Other."""
    totals, colors = {}, {}
    for name, color, count in rows:
        if count > 0:
            totals[name] = totals.get(name, 0) + count
            colors[name] = color
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [(name, colors[name], n) for name, n in ranked[:top]]
    rest = sum(n for _, n in ranked[top:])
    if rest:
        out.append(("Other", OTHER_COLOR, rest))
    return out


def _arc_path(cx, cy, r_out, r_in, a0, a1):
    """Donut slice from angle a0 to a1 (radians), drawn as two half arcs so a full circle works too."""
    am = (a0 + a1) / 2

    def pt(r, a):
        return f"{cx + r * math.cos(a):.2f} {cy + r * math.sin(a):.2f}"
    return (f"M {pt(r_out, a0)} A {r_out} {r_out} 0 0 1 {pt(r_out, am)} A {r_out} {r_out} 0 0 1 {pt(r_out, a1)} "
            f"L {pt(r_in, a1)} A {r_in} {r_in} 0 0 0 {pt(r_in, am)} A {r_in} {r_in} 0 0 0 {pt(r_in, a0)} Z")


def neon_colors(langs):
    colors, rank = [], 0
    for name, _, _ in langs:
        if name == "Other":
            colors.append(OTHER_NEON)
        else:
            colors.append(NEON[rank % len(NEON)])
            rank += 1
    return colors


def pie_group(langs):
    total = sum(n for _, _, n in langs)
    colors = neon_colors(langs)
    g = ET.Element(f"{{{SVG}}}g", {"transform": PIE_TRANSFORM})
    defs = ET.SubElement(g, f"{{{SVG}}}defs")
    glow = ET.SubElement(defs, f"{{{SVG}}}filter", {"id": "neon", "x": "-30%", "y": "-30%", "width": "160%", "height": "160%"})
    ET.SubElement(glow, f"{{{SVG}}}feGaussianBlur", {"in": "SourceGraphic", "stdDeviation": "5", "result": "blur"})
    merge = ET.SubElement(glow, f"{{{SVG}}}feMerge")
    ET.SubElement(merge, f"{{{SVG}}}feMergeNode", {"in": "blur"})
    ET.SubElement(merge, f"{{{SVG}}}feMergeNode", {"in": "SourceGraphic"})
    ring = ET.SubElement(g, f"{{{SVG}}}g", {"filter": "url(#neon)"})
    a = -math.pi / 2
    for (_, _, n), color in zip(langs, colors):
        a1 = a + 2 * math.pi * n / total
        ET.SubElement(ring, f"{{{SVG}}}path", {"d": _arc_path(130, 130, 125, 68, a, a1), "fill": color,
                                                "class": "stroke-bg", "stroke-width": "2px"})
        a = a1
    legend = ET.SubElement(g, f"{{{SVG}}}g", {"transform": "translate(273, 0)"})
    size, step = 21.67, 32.5
    top = 130 - step * len(langs) / 2
    for i, ((name, _, n), color) in enumerate(zip(langs, colors)):
        y = top + i * step
        ET.SubElement(legend, f"{{{SVG}}}rect", {"x": "0", "y": f"{y + 5.4:.2f}", "width": f"{size}",
                                                  "height": f"{size}", "fill": color, "class": "stroke-bg",
                                                  "stroke-width": "1px"})
        text = ET.SubElement(legend, f"{{{SVG}}}text", {"dominant-baseline": "middle", "x": "30",
                                                         "y": f"{y + 16.25:.2f}", "class": "fill-fg",
                                                         "font-size": f"{size}px"})
        text.text = f"{name} {round(100 * n / total)}%"
    return g


def replace_pie(svg_text, langs):
    if "<!DOCTYPE" in svg_text or "<!ENTITY" in svg_text:
        raise ValueError("unexpected DOCTYPE/ENTITY in the graph")
    ET.register_namespace("", SVG)
    root = ET.fromstring(svg_text)
    pies = [i for i, el in enumerate(root) if el.tag == f"{{{SVG}}}g" and el.get("transform") == PIE_TRANSFORM]
    if len(pies) != 1:
        raise ValueError(f"expected one pie group at {PIE_TRANSFORM}, found {len(pies)}")
    root.remove(root[pies[0]])
    root.insert(pies[0], pie_group(langs))
    return ET.tostring(root, encoding="unicode")


def main(argv):
    path = argv[0]
    token = os.environ.get("LANGS_TOKEN")
    if not token:
        print("LANGS_TOKEN is not set; keeping the graph tool's public-only pie.", file=sys.stderr)
        return 0
    langs = aggregate(fetch(token))
    if not langs:
        print("No commits found in the last 365 days; keeping the graph tool's pie.", file=sys.stderr)
        return 0
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(replace_pie(text, langs))
    total = sum(n for _, _, n in langs)
    print("Languages:", ", ".join(f"{name} {round(100 * n / total)}%" for name, _, n in langs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
