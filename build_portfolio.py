#!/usr/bin/env python3
"""Build the GitHub profile README (+ animated SVG parts) from index.html.

index.html is the single source of truth: edit your portfolio there, run this
script, and the README, the SVG pieces in assets/ and the layout all follow.

    pip install requests
    python build_portfolio.py     # writes README.md and assets/*.svg
    python today.py               # fills in the live GitHub numbers

GitHub can't run JavaScript or CSS in a README, so the interactive parts are
rebuilt with things GitHub *does* support:
  - animated SVG images (hero title, flash block, marquee)  -> look & motion
  - <a> links wrapped around SVG buttons                    -> clickable buttons/nav
  - nested <details>                                        -> tabs + open/close items
The full original page (real tabs, hover, scroll reveal) is index.html itself,
which you can host with GitHub Pages.
"""
import base64
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "index.html")
ASSETS = os.path.join(HERE, "assets")
CACHE = os.path.join(HERE, "cache")
PAGES_URL = "https://kronix-k.github.io/kronix-k/"
W = 900  # width of every SVG part

DISPLAY = "'Dela Gothic One','Arial Black','Impact','Segoe UI',sans-serif"
BODY = "'Zen Kaku Gothic New','Segoe UI',Arial,'Segoe UI Emoji','Apple Color Emoji',sans-serif"

LIGHT = dict(bg="#DCD5F2", ink="#1E1433", muted="#4D4366", accent="#D81B6A", block="#F6D743",
             block_ink="#1E1433", panel="#EFEAFB", add="#2E7D32", dele="#C62828")
DARK = dict(bg="#1A1230", ink="#EDE7FF", muted="#B5A9D6", accent="#FF5C9E", block="#F6D743",
            block_ink="#1E1433", panel="#251A44", add="#81C784", dele="#E57373")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape(str(s), quote=True)


def units(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def tw(s, size, k=0.58):
    """Rough text width in px."""
    return round(units(s) * size * k)


def wrap(text, limit):
    lines, cur = [], ""
    for tok in re.findall(r"\S+\s*", text):
        if cur and units(cur + tok.rstrip()) > limit:
            lines.append(cur.rstrip())
            cur = ""
        cur += tok
    if cur:
        lines.append(cur.rstrip())
    return lines or [""]


def slug(text):
    """GitHub's heading anchor: lowercase, drop punctuation, spaces -> hyphens."""
    t = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"\s", "-", t.strip())


def http_get(url, ua=True):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest())
    if os.path.exists(path):
        return open(path, "rb").read()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"} if ua else {}
    r = requests.get(url, headers=headers, timeout=40)
    r.raise_for_status()
    open(path, "wb").write(r.content)
    return r.content


def load_fonts():
    """Latin subsets of the portfolio's Google Fonts, as base64 @font-face rules."""
    families = [
        ("Dela Gothic One", "https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=swap"),
        ("Zen Kaku Gothic New",
         "https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;700&display=swap"),
    ]
    out = []
    for fam, url in families:
        try:
            css = http_get(url).decode()
            for subset, body in re.findall(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", css, re.S):
                if subset != "latin":
                    continue
                weight = re.search(r"font-weight:\s*(\d+)", body).group(1)
                src = re.search(r"url\((https?://[^)]+)\)", body).group(1)
                b64 = base64.b64encode(http_get(src, ua=False)).decode()
                out.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};"
                           f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! font '{fam}' not embedded (fallback fonts will be used): {e}", file=sys.stderr)
    return "".join(out)


# --------------------------------------------------------------------------- #
# read index.html
# --------------------------------------------------------------------------- #
def parse_source():
    s = open(SRC, encoding="utf-8").read()
    u = html.unescape

    def one(pattern, flags=re.S):
        m = re.search(pattern, s, flags)
        if not m:
            sys.exit(f"index.html: could not find {pattern[:50]}")
        return m

    d = {}
    d["title"] = one(r'<h1 id="title" aria-label="(.*?)"').group(1)
    d["flash"] = u(one(r'<div class="flash">(.*?)</div>').group(1))
    d["intro"] = u(one(r'<header class="hero">.*?<p>(.*?)</p>').group(1))
    d["buttons"] = [(("primary" in c), h, u(t)) for c, h, t in
                    re.findall(r'<a class="btn([^"]*)" href="([^"]+)"[^>]*>(.*?)</a>',
                               one(r'<div class="btns">(.*?)</div>').group(1))]
    d["nav"] = [(h, u(t)) for h, t in re.findall(r'<a href="(#[^"]+)">(.*?)</a>', one(r"<nav.*?</nav>").group(0))]
    mq = one(r'getElementById\("mq"\)\.textContent="(.*?)"\.repeat').group(1)
    d["marquee"] = json.loads(f'"{mq}"')

    d["sections"] = {}
    for sid in ("projects", "skills", "log", "contact"):
        blk = one(rf'<section id="{sid}">(.*?)</section>').group(1)
        h2 = u(re.search(r"<h2>(.*?)</h2>", blk).group(1))
        sub = u(re.search(r'<p class="sub">(.*?)</p>', blk).group(1))
        d["sections"][sid] = {"h2": h2, "sub": sub, "html": blk}

    d["projects"] = [
        {"main": bool(m), "name": u(n), "tag": u(t), "desc": u(p)}
        for m, n, t, p in re.findall(
            r'<div class="proj( main)?">\s*<div><h3>(.*?)</h3>(?:<span class="tag">(.*?)</span>)?</div>\s*<p>(.*?)</p>',
            d["sections"]["projects"]["html"], re.S)]
    sk = re.search(r'<div class="skills">(.*?)</div>', d["sections"]["skills"]["html"], re.S).group(1)
    d["skills"] = [u(x) for x in re.findall(r"<span>(.*?)</span>", sk)]
    d["footer"] = [u(x) for x in re.findall(r"<span>(.*?)</span>", one(r"<footer>(.*?)</footer>").group(1))]
    d["contact_btn"] = re.search(r'<a class="btn primary" href="([^"]+)"[^>]*>(.*?)</a>',
                                 d["sections"]["contact"]["html"])

    script = one(r"var DATA = \{(.*?)\n\};").group(1)
    cut = script.index("games:")
    entry = re.compile(r'\{t:"([^"]*)",\s*r:"([^"]*)",\s*m:"([^"]*)",\s*(?:u:"([^"]*)",\s*)?n:"([^"]*)"\}')

    def entries(chunk):
        return [dict(t=t, r=r, m=m, u=url, n=n) for t, r, m, url, n in entry.findall(chunk)]

    d["anime"], d["games"] = entries(script[:cut]), entries(script[cut:])
    return d


# --------------------------------------------------------------------------- #
# svg parts
# --------------------------------------------------------------------------- #
def svg_doc(w, h, body, pal, fonts, label, css=""):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<style>
{fonts}
text{{font-family:{BODY};}}
.disp{{font-family:{DISPLAY};font-weight:400;}}
{css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;}}}}
</style>
<rect width="{w}" height="{h}" fill="{pal["bg"]}"/>
{body}
</svg>
'''


def t(x, y, s, size=17, fill="#000", weight=400, anchor=None, cls="", extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    c = f' class="{cls}"' if cls else ""
    return (f'<text x="{x}" y="{y}"{a}{c} font-size="{size}" font-weight="{weight}" fill="{fill}"{extra}>'
            f"{esc(s)}</text>")


# em advance widths for the big animated title (Dela Gothic One-like heavy face)
ADV = {"k": .66, "r": .58, "o": .68, "n": .66, "i": .36, "x": .66, "-": .42}


def part_hero(d, pal, fonts):
    size, x0, base = 138, 44, 175
    letters, x = [], x0
    for i, ch in enumerate(d["title"]):
        adv = ADV.get(ch, .65) * size
        letters.append(
            f'<text class="L disp" style="--i:{i}" x="{x + adv / 2:.1f}" y="{base}" text-anchor="middle" '
            f'fill="{pal["accent"]}" aria-hidden="true">{esc(ch)}</text>')
        x += adv
    # flash block (wraps like max-width:34ch)
    fl = wrap(d["flash"], 34)
    fw = max(tw(l, 19, .56) for l in fl) + 40
    fh = len(fl) * 30 + 20
    fy = 232
    flash = f'<clipPath id="wipe"><rect x="{x0}" y="{fy}" width="0" height="{fh}">' \
            f'<animate attributeName="width" from="0" to="{fw}" begin="1s" dur=".7s" fill="freeze" ' \
            f'calcMode="spline" keyTimes="0;1" keySplines=".7 0 .2 1"/></rect></clipPath>' \
            f'<g clip-path="url(#wipe)"><rect x="{x0}" y="{fy}" width="{fw}" height="{fh}" fill="{pal["block"]}"/>'
    for k, l in enumerate(fl):
        flash += t(x0 + 20, fy + 34 + k * 30, l, 19, pal["block_ink"], 700)
    flash += "</g>"
    # intro paragraph
    py = fy + fh + 44
    ps = "".join(t(x0, py + k * 28, l, 17, pal["muted"]) for k, l in enumerate(wrap(d["intro"], 56)))
    h = py + 28 * len(wrap(d["intro"], 56)) + 20
    body = (f'<g transform="rotate(-3 {x0} {base + 30})">{"".join(letters)}</g>'
            f'{flash}<g class="fu">{ps}</g>')
    css = (f".L{{font-size:{size}px;transform-box:fill-box;transform-origin:center;"
           "animation:drop .8s cubic-bezier(.2,.9,.3,1.3) both,wave 3s ease-in-out infinite;"
           "animation-delay:calc(var(--i)*80ms),calc(1s + var(--i)*140ms);}"
           "@keyframes drop{from{transform:translateY(-1.2em) rotate(-25deg) scale(.4);opacity:0;}}"
           "@keyframes wave{0%,100%{transform:translateY(0);}50%{transform:translateY(-.08em);}}"
           ".fu{animation:fadeUp .7s ease 1.3s both;}"
           "@keyframes fadeUp{from{opacity:0;transform:translateY(18px);}}")
    return W, h, svg_doc(W, h, body, pal, fonts, f'{d["title"]} - {d["flash"]}', css)


def part_marquee(d, pal, fonts):
    h = 92
    seg = d["marquee"]
    half = tw(seg * 4, 20, .66)
    text = seg * 8
    body = (f'<g transform="rotate(-1.5 {W / 2} {h / 2})"><rect x="-40" y="22" width="{W + 80}" height="48" fill="{pal["ink"]}"/>'
            f'<g><animateTransform attributeName="transform" type="translate" from="0 0" to="-{half} 0" '
            f'dur="40s" repeatCount="indefinite"/>'
            f'<text class="disp" x="0" y="54" font-size="20" fill="{pal["bg"]}" xml:space="preserve" '
            f'textLength="{half * 2}" lengthAdjust="spacing">{esc(text)}</text></g></g>')
    return W, h, svg_doc(W, h, body, pal, fonts, "Low-level systems, interactive UIs, constant learning")


def part_button(label, primary, pal, fonts, size=17):
    w, h = tw(label, size, .6) + 44, 48
    if primary:
        body = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="{pal["ink"]}"/>'
                + t(w / 2, 31, label, size, pal["bg"], 700, "middle"))
    else:
        body = (f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" fill="{pal["bg"]}" stroke="{pal["ink"]}" stroke-width="2"/>'
                + t(w / 2, 31, label, size, pal["ink"], 700, "middle"))
    return w, h, svg_doc(w, h, body, pal, fonts, label)


def part_nav(label, pal, fonts):
    w, h = tw(label, 17, .6) + 24, 40
    body = (t(w / 2, 24, label, 17, pal["ink"], 700, "middle")
            + f'<rect x="12" y="32" width="{w - 24}" height="3" fill="{pal["accent"]}"/>')
    return w, h, svg_doc(w, h, body, pal, fonts, label)


def part_projects(d, pal, fonts):
    y, parts = 0, []
    for k, p in enumerate(d["projects"]):
        top = y + (0 if k == 0 else 22)
        desc = wrap(p["desc"], 54)
        right_h = len(desc) * 28
        left_h = (40 if p["main"] else 28) + (34 if p["tag"] else 0)
        row_h = max(right_h, left_h)
        if p["main"]:
            parts.append(f'<text class="disp" x="24" y="{top + 30}" font-size="27" fill="{pal["accent"]}">{esc(p["name"])}</text>')
        else:
            parts.append(t(24, top + 22, p["name"], 20, pal["ink"], 700))
        if p["tag"]:
            ty = top + (46 if p["main"] else 34)
            tww = tw(p["tag"], 13.6, .6) + 22
            parts.append(f'<rect x="24" y="{ty - 18}" width="{tww}" height="25" fill="{pal["block"]}"/>'
                         + t(24 + tww / 2, ty, p["tag"], 13.6, pal["block_ink"], 700, "middle"))
        for j, l in enumerate(desc):
            parts.append(t(340, top + 22 + j * 28, l, 17, pal["muted"]))
        y = top + row_h + 22
        parts.append(f'<rect x="24" y="{y - 1}" width="{W - 48}" height="1" fill="{pal["ink"]}"/>')
    h = y + 12
    return W, h, svg_doc(W, h, "".join(parts), pal, fonts, "Projects: " + ", ".join(p["name"] for p in d["projects"]))


def part_skills(d, pal, fonts):
    x, y, parts = 24, 12, []
    for s in d["skills"]:
        w = tw(s, 17, .6) + 36
        if x + w > W - 24:
            x, y = 24, y + 52
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="42" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2"/>'
                     + t(x + w / 2, y + 28, s, 17, pal["ink"], 700, "middle"))
        x += w + 10
    h = y + 42 + 14
    return W, h, svg_doc(W, h, "".join(parts), pal, fonts, "Languages and tools: " + ", ".join(d["skills"]))


def part_stats(pal, fonts):
    tw_, th, gap, x0 = 204, 96, 12, 24
    tiles = [("Streak", "streak_data", "days"), ("Stars", "star_data", ""), ("Repos", "repo_data", ""),
             ("Contribs", "contrib_data", ""), ("Commits", "commit_data", ""), ("Followers", "follower_data", "")]
    parts = []
    for i, (lab, tid, _) in enumerate(tiles):
        row, col = divmod(i, 4)
        x, y = x0 + col * (tw_ + gap), 24 + row * (th + gap)
        parts.append(f'<rect x="{x}" y="{y}" width="{tw_}" height="{th}" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2"/>'
                     + t(x + 16, y + 30, lab.upper(), 12, pal["muted"], 700, extra=' letter-spacing="1"')
                     + f'<text id="{tid}" class="disp" x="{x + 16}" y="{y + 70}" font-size="32" '
                       f'fill="{pal["accent"] if i % 2 else pal["ink"]}">0</text>')
    # lines-of-code tile (wide)
    x, y, w, h = x0 + 2 * (tw_ + gap), 24 + th + gap, 2 * tw_ + gap, 120
    bar = w - 32
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2"/>'
                 + t(x + 16, y + 30, "LINES OF CODE", 12, pal["muted"], 700, extra=' letter-spacing="1"')
                 + f'<text id="loc_data" class="disp" x="{x + 16}" y="{y + 70}" font-size="32" fill="{pal["ink"]}">0</text>'
                 + f'<rect x="{x + 16}" y="{y + 82}" width="{bar}" height="8" fill="{pal["bg"]}"/>'
                 + f'<rect id="loc_bar" x="{x + 16}" y="{y + 82}" width="0" height="8" fill="{pal["accent"]}"/>'
                 + f'<text id="loc_add" x="{x + 16}" y="{y + 110}" font-size="12" font-weight="700" fill="{pal["add"]}">++ 0</text>'
                 + f'<text id="loc_del" x="{x + w - 16}" y="{y + 110}" text-anchor="end" font-size="12" font-weight="700" fill="{pal["dele"]}">-- 0</text>')
    height = 24 + th + gap + h + 24
    return W, height, svg_doc(W, height, "".join(parts), pal, fonts, "GitHub stats")


def part_footer(d, pal, fonts):
    h = 92
    body = (f'<rect x="24" y="0" width="{W - 48}" height="2" fill="{pal["ink"]}"/>'
            + t(24, 56, d["footer"][0], 17, pal["muted"])
            + t(W - 24, 56, d["footer"][1], 17, pal["muted"], anchor="end"))
    return W, h, svg_doc(W, h, body, pal, fonts, " - ".join(d["footer"]))


# --------------------------------------------------------------------------- #
# README
# --------------------------------------------------------------------------- #
class Assets:
    def __init__(self, fonts):
        self.fonts, self.size = fonts, {}
        os.makedirs(ASSETS, exist_ok=True)

    def make(self, name, fn, *args):
        for theme, pal in (("light", LIGHT), ("dark", DARK)):
            w, h, svg = fn(*args, pal, self.fonts)
            with open(os.path.join(ASSETS, f"{name}_{theme}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            self.size[name] = (w, h)
        return name

    def pic(self, name, alt, scale=1.0, link=None):
        w, h = self.size[name]
        img = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}_dark.svg">'
               f'<source media="(prefers-color-scheme: light)" srcset="assets/{name}_light.svg">'
               f'<img src="assets/{name}_light.svg" alt="{esc(alt)}" width="{round(w * scale)}" height="{round(h * scale)}"></picture>')
        return f'<a href="{esc(link)}">{img}</a>' if link else img


def entry_html(e):
    note = f"<p>{esc(e['n'])}</p>"
    link = f'<p><a href="{esc(e["u"])}">View on Steam</a></p>' if e.get("u") else ""
    return (f"<details>\n<summary><b>{esc(e['t'])}</b> &nbsp;·&nbsp; <i>{esc(e['r'])}</i></summary>\n"
            f"<blockquote><sub>{esc(e['m'])}</sub>{note}{link}</blockquote>\n</details>\n")


def build_readme(d, a):
    S = d["sections"]
    nav_names = {}
    for href, label in d["nav"]:
        sid = href.lstrip("#")
        a.make(f"nav_{sid}", part_nav, label)
        nav_names[href] = (f"nav_{sid}", label)
    a.make("hero", part_hero, d)
    a.make("marquee", part_marquee, d)
    btns = []
    for i, (primary, href, label) in enumerate(d["buttons"]):
        a.make(f"btn_{i}", part_button, label, primary)
        btns.append((f"btn_{i}", label, href))
    a.make("btn_live", part_button, "Interactive version", False)
    a.make("projects", part_projects, d)
    a.make("skills", part_skills, d)
    a.make("tab_anime", part_button, "Anime", False)
    a.make("tab_games", part_button, "Games", False)
    cbtn = d["contact_btn"]
    a.make("btn_contact", part_button, html.unescape(cbtn.group(2)), True)
    a.make("stats", part_stats)
    a.make("footer", part_footer, d)

    def anchor(href):  # '#projects' -> GitHub heading slug of that section
        sid = href.lstrip("#")
        return "#" + slug(S[sid]["h2"]) if sid in S else href

    nav = "&nbsp;".join(a.pic(n, lbl, link=anchor(h)) for h, (n, lbl) in nav_names.items())
    buttons = "&nbsp;&nbsp;".join(
        a.pic(n, lbl, link=anchor(h) if h.startswith("#") else h) for n, lbl, h in btns)
    buttons += "&nbsp;&nbsp;" + a.pic("btn_live", "Interactive version", link=PAGES_URL)

    anime = "\n".join(entry_html(e) for e in d["anime"])
    games = "\n".join(entry_html(e) for e in d["games"])
    return f'''<p align="right">{nav}</p>

{a.pic("hero", d["title"])}

<p>{buttons}</p>

{a.pic("marquee", "Low-level systems ✦ Interactive UIs ✦ Constant learning")}

## {S["projects"]["h2"]}

{S["projects"]["sub"]}

{a.pic("projects", "Projects")}

## {S["skills"]["h2"]}

{S["skills"]["sub"]}

{a.pic("skills", "Skills")}

## {S["log"]["h2"]}

{S["log"]["sub"]} *(Click a tab, then a title.)*

<details open>
<summary>{a.pic("tab_anime", "Anime")}</summary>

{anime}
</details>

<details>
<summary>{a.pic("tab_games", "Games")}</summary>

{games}
</details>

## {S["contact"]["h2"]}

{S["contact"]["sub"]}

{a.pic("btn_contact", "GitHub", link=cbtn.group(1))}

## GitHub stats

{a.pic("stats", "GitHub stats")}

{a.pic("footer", " - ".join(d["footer"]))}
'''


def main():
    d = parse_source()
    print(f"parsed: {len(d['projects'])} projects, {len(d['skills'])} skills, "
          f"{len(d['anime'])} anime, {len(d['games'])} games")
    fonts = load_fonts()
    print("fonts embedded" if fonts else "fonts NOT embedded (fallback stack)")
    a = Assets(fonts)
    readme = build_readme(d, a)
    open(os.path.join(HERE, "README.md"), "w", encoding="utf-8").write(readme)
    print(f"wrote README.md and {len(os.listdir(ASSETS))} SVG files in assets/")


if __name__ == "__main__":
    main()
