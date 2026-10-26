#!/usr/bin/env python3
"""Build the GitHub profile README from index.html.

index.html is the single source of truth: edit your portfolio there, run this
script, and README.md + assets/profile_light.svg / profile_dark.svg follow.

    pip install requests
    python build_portfolio.py     # writes README.md and the two SVGs
    python today.py               # fills in the live GitHub numbers

The README is ONE animated SVG (light + dark). GitHub shows README images with
no JavaScript and no clicks, so everything that needed a mouse is animation:
  - tabs Anime / Games        -> the logbook auto-plays: tab, list row and note card
                                 advance together, with a progress bar
  - click-to-open items       -> each entry "opens" in turn
  - hover effects (nav, buttons, project rows, chips, stat tiles) -> play in sequence
The full interactive page is still index.html (host it with GitHub Pages).
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


def t(x, y, s, size=17, fill="#000", weight=400, anchor=None, cls="", extra=""):
    a = f' text-anchor="{anchor}"' if anchor else ""
    c = f' class="{cls}"' if cls else ""
    return (f'<text x="{x}" y="{y}"{a}{c} font-size="{size}" font-weight="{weight}" fill="{fill}"{extra}>'
            f"{esc(s)}</text>")


# --------------------------------------------------------------------------- #
# animation helpers
# --------------------------------------------------------------------------- #
def kf(name, stops):
    """@keyframes from [(percent, css), ...]."""
    return "@keyframes %s{%s}" % (name, "".join(f"{p:.3f}%{{{c}}}" for p, c in stops))


def win(name, start, end, tot, ramp, on, off):
    """Keyframes that are `on` between start..end (seconds) of a `tot`-second loop."""
    a, b, r = start / tot * 100, end / tot * 100, ramp / tot * 100
    stops = [(0, off)]
    if a > 0:
        stops.append((a, off))
    stops += [(a + r, on), (b - r, on)]
    if b < 100 - 1e-6:
        stops.append((b, off))
    stops.append((100, off))
    return kf(name, stops)


def head(h2, sub, pal):
    """Section top rule + big heading + subtitle. Returns (svg, y where content starts)."""
    out = [f'<rect x="24" y="0" width="{W - 48}" height="2" fill="{pal["ink"]}"/>',
           f'<text class="disp" x="24" y="100" font-size="42" fill="{pal["ink"]}">{esc(h2)}</text>']
    y = 140
    for line in wrap(sub, 78):
        out.append(t(24, y, line, 17, pal["muted"]))
        y += 27
    return "".join(out), y + 18


# --------------------------------------------------------------------------- #
# sections (each returns height, svg fragment, css)
# --------------------------------------------------------------------------- #
def sec_nav(d, pal):
    h, gap, step = 54, 22, 3
    labels = [lbl for _, lbl in d["nav"]]
    widths = [tw(l, 17, .6) + 24 for l in labels]
    x = W - 44 - (sum(widths) + gap * (len(labels) - 1))
    parts = []
    for i, (l, w) in enumerate(zip(labels, widths)):
        dl = f'style="animation-delay:{i * step}s"'
        parts.append(f'<text class="nvt" x="{x + w / 2:.1f}" y="32" text-anchor="middle" font-size="17" '
                     f'font-weight="700" fill="{pal["ink"]}" {dl}>{esc(l)}</text>'
                     f'<rect class="nvu" x="{x + 12:.1f}" y="40" width="{w - 24:.1f}" height="3" '
                     f'fill="{pal["accent"]}" {dl}/>')
        x += w + gap
    tot = step * len(labels)
    css = (win("nv_t", 0, step, tot, .3, f'fill:{pal["accent"]}', f'fill:{pal["ink"]}')
           + win("nv_u", 0, step, tot, .3, "transform:scaleX(1)", "transform:scaleX(0)")
           + f".nvt{{animation:nv_t {tot}s infinite both;}}"
             f".nvu{{transform-box:fill-box;transform-origin:left center;transform:scaleX(0);"
             f"animation:nv_u {tot}s infinite both;}}")
    return h, "".join(parts), css


# em advance widths for the big animated title (heavy display face)
ADV = {"k": .66, "r": .58, "o": .68, "n": .66, "i": .36, "x": .66, "-": .42}


def sec_hero(d, pal):
    size, x0, base = 138, 44, 175
    letters, x = [], x0
    for i, ch in enumerate(d["title"]):
        adv = ADV.get(ch, .65) * size
        letters.append(
            f'<text class="L disp" style="--i:{i}" x="{x + adv / 2:.1f}" y="{base}" text-anchor="middle" '
            f'fill="{pal["accent"]}" aria-hidden="true">{esc(ch)}</text>')
        x += adv
    fl = wrap(d["flash"], 34)
    fw = max(tw(l, 19, .56) for l in fl) + 40
    fh = len(fl) * 30 + 20
    fy = 232
    flash = (f'<clipPath id="wipe"><rect x="{x0}" y="{fy}" width="0" height="{fh}">'
             f'<animate attributeName="width" values="0;{fw};{fw};0" keyTimes="0;.08;.92;1" dur="14s" '
             f'begin="1s" repeatCount="indefinite" calcMode="spline" '
             f'keySplines=".7 0 .2 1;0 0 1 1;.7 0 .2 1"/></rect></clipPath>'
             f'<g clip-path="url(#wipe)"><rect x="{x0}" y="{fy}" width="{fw}" height="{fh}" fill="{pal["block"]}"/>')
    for k, l in enumerate(fl):
        flash += t(x0 + 20, fy + 34 + k * 30, l, 19, pal["block_ink"], 700)
    flash += "</g>"
    py = fy + fh + 44
    intro = wrap(d["intro"], 56)
    ps = "".join(t(x0, py + k * 28, l, 17, pal["muted"]) for k, l in enumerate(intro))
    h = py + 28 * len(intro) + 16
    body = (f'<g transform="rotate(-3 {x0} {base + 30})">{"".join(letters)}</g>'
            f'{flash}<g class="fu">{ps}</g>')
    css = (f".L{{font-size:{size}px;transform-box:fill-box;transform-origin:center;"
           "animation:drop .8s cubic-bezier(.2,.9,.3,1.3) both,wave 3s ease-in-out infinite;"
           "animation-delay:calc(var(--i)*80ms),calc(1s + var(--i)*140ms);}"
           "@keyframes drop{from{transform:translateY(-1.2em) rotate(-25deg) scale(.4);opacity:0;}}"
           "@keyframes wave{0%,100%{transform:translateY(0);}50%{transform:translateY(-.08em);}}"
           ".fu{animation:fadeUp .7s ease 1.3s both;}"
           "@keyframes fadeUp{from{opacity:0;transform:translateY(18px);}}")
    return h, body, css


def sec_buttons(d, pal):
    """The two hero buttons. The 'hover' state that used to need a mouse now plays by itself."""
    h, x, tot, step = 84, 44, 6, 3
    parts = []
    for i, (primary, _href, label) in enumerate(d["buttons"][:2]):
        w = tw(label, 17, .6) + 44
        dl = f'style="animation-delay:{i * step}s"'
        if primary:
            shape = (f'<rect class="bpr" x="1" y="1" width="{w - 2}" height="46" fill="{pal["ink"]}" {dl}/>'
                     + f'<text class="bpt" x="{w / 2}" y="31" text-anchor="middle" font-size="17" '
                       f'font-weight="700" fill="{pal["bg"]}" {dl}>{esc(label)}</text>')
        else:
            shape = (f'<rect class="bsr" x="2" y="2" width="{w - 4}" height="44" fill="{pal["bg"]}" '
                     f'stroke="{pal["ink"]}" stroke-width="2" {dl}/>'
                     + f'<text class="bst" x="{w / 2}" y="31" text-anchor="middle" font-size="17" '
                       f'font-weight="700" fill="{pal["ink"]}" {dl}>{esc(label)}</text>')
        parts.append(f'<g transform="translate({x},18)"><g class="bg" {dl}>{shape}</g></g>')
        x += w + 14
    css = (win("bt_g", 0, step, tot, .3, "transform:translateY(-3px) rotate(-1.5deg)", "transform:none")
           + win("bt_pr", 0, step, tot, .3, f'fill:{pal["accent"]}', f'fill:{pal["ink"]}')
           + win("bt_pt", 0, step, tot, .3, "fill:#fff", f'fill:{pal["bg"]}')
           + win("bt_sr", 0, step, tot, .3, f'fill:{pal["accent"]};stroke:{pal["accent"]}',
                 f'fill:{pal["bg"]};stroke:{pal["ink"]}')
           + win("bt_st", 0, step, tot, .3, "fill:#fff", f'fill:{pal["ink"]}')
           + f".bg{{transform-box:fill-box;transform-origin:center;animation:bt_g {tot}s infinite both;}}"
             f".bpr{{animation:bt_pr {tot}s infinite both;}}.bpt{{animation:bt_pt {tot}s infinite both;}}"
             f".bsr{{animation:bt_sr {tot}s infinite both;}}.bst{{animation:bt_st {tot}s infinite both;}}")
    return h, "".join(parts), css


def sec_marquee(d, pal):
    h = 92
    seg = d["marquee"]
    half = tw(seg * 4, 20, .66)
    text = seg * 8
    body = (f'<g transform="rotate(-1.5 {W / 2} {h / 2})"><rect x="-40" y="22" width="{W + 80}" height="48" fill="{pal["ink"]}"/>'
            f'<g><animateTransform attributeName="transform" type="translate" from="0 0" to="-{half} 0" '
            f'dur="40s" repeatCount="indefinite"/>'
            f'<text class="disp" x="0" y="54" font-size="20" fill="{pal["bg"]}" xml:space="preserve" '
            f'textLength="{half * 2}" lengthAdjust="spacing">{esc(text)}</text></g></g>')
    return h, body, ""


def sec_projects(d, pal):
    S = d["sections"]["projects"]
    hd, y0 = head(S["h2"], S["sub"], pal)
    y, parts = 0, []
    n, step = len(d["projects"]), 3
    for k, p in enumerate(d["projects"]):
        top = y + (0 if k == 0 else 22)
        desc = wrap(p["desc"], 54)
        left_h = (40 if p["main"] else 28) + (34 if p["tag"] else 0) + (12 if p["main"] else 0)
        row_h = max(len(desc) * 28, left_h)
        dl = f'style="animation-delay:{k * step}s"'
        g = []
        if p["main"]:
            g.append(f'<text class="disp" x="24" y="{top + 30}" font-size="27" fill="{pal["accent"]}">{esc(p["name"])}</text>')
        else:
            g.append(f'<text class="pn" x="24" y="{top + 22}" font-size="20" font-weight="700" fill="{pal["ink"]}" {dl}>{esc(p["name"])}</text>')
        if p["tag"]:
            ty = top + (60 if p["main"] else 34)
            tww = tw(p["tag"], 13.6, .6) + 22
            g.append(f'<rect x="24" y="{ty - 18}" width="{tww}" height="25" fill="{pal["block"]}"/>'
                     + t(24 + tww / 2, ty, p["tag"], 13.6, pal["block_ink"], 700, "middle"))
        for j, l in enumerate(desc):
            g.append(t(340, top + 22 + j * 28, l, 17, pal["muted"]))
        parts.append(f'<g class="pr" {dl}>{"".join(g)}</g>')
        y = top + row_h + 22
        parts.append(f'<rect x="24" y="{y - 1}" width="{W - 48}" height="1" fill="{pal["ink"]}"/>')
    tot = n * step
    css = (win("pr_g", 0, step, tot, .35, "transform:translateX(10px)", "transform:none")
           + win("pr_n", 0, step, tot, .35, f'fill:{pal["accent"]}', f'fill:{pal["ink"]}')
           + f".pr{{animation:pr_g {tot}s infinite both;}}.pn{{animation:pr_n {tot}s infinite both;}}")
    body = hd + f'<g transform="translate(0,{y0})">{"".join(parts)}</g>'
    return y0 + y + 56, body, css


def sec_skills(d, pal):
    S = d["sections"]["skills"]
    hd, y0 = head(S["h2"], S["sub"], pal)
    x, y, parts = 24, 12, []
    n, step = len(d["skills"]), 1.5
    for i, s in enumerate(d["skills"]):
        w = tw(s, 17, .6) + 36
        if x + w > W - 24:
            x, y = 24, y + 52
        dl = f'style="animation-delay:{i * step}s"'
        parts.append(f'<g transform="translate({x},{y})"><g class="ch" {dl}>'
                     f'<rect class="chb" width="{w}" height="42" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2" {dl}/>'
                     f'<text class="cht" x="{w / 2}" y="28" text-anchor="middle" font-size="17" font-weight="700" fill="{pal["ink"]}" {dl}>{esc(s)}</text>'
                     f'</g></g>')
        x += w + 10
    tot = n * step
    css = (win("sk_g", 0, step, tot, .25, "transform:rotate(-4deg) scale(1.08)", "transform:none")
           + win("sk_b", 0, step, tot, .25, f'fill:{pal["block"]}', f'fill:{pal["panel"]}')
           + win("sk_t", 0, step, tot, .25, f'fill:{pal["block_ink"]}', f'fill:{pal["ink"]}')
           + f".ch{{transform-box:fill-box;transform-origin:center;animation:sk_g {tot}s infinite both;}}"
             f".chb{{animation:sk_b {tot}s infinite both;}}.cht{{animation:sk_t {tot}s infinite both;}}")
    return y0 + y + 42 + 56, hd + f'<g transform="translate(0,{y0})">{"".join(parts)}</g>', css


# ---- logbook: tabs + accordion rebuilt as an auto-playing slideshow ------- #
LIST_W, ROW_H, PAD = 404, 54, 22


def steam_id(url):
    m = re.search(r"/app/(\d+)", url or "")
    return f"store.steampowered.com/app/{m.group(1)}" if m else "store.steampowered.com"


def sec_log(d, pal):
    S = d["sections"]["log"]
    sub = re.sub(r"\s*Tap a title to read my notes\.?", " The notes play on their own.", S["sub"])
    hd, y0 = head(S["h2"], sub, pal)

    entries = [dict(e, kind="anime") for e in d["anime"]] + [dict(e, kind="games") for e in d["games"]]
    counts = {"anime": len(d["anime"]), "games": len(d["games"])}
    px = 24 + LIST_W + 20
    pw = W - 24 - px
    inner = pw - 2 * PAD

    # layout of every detail card + how long it stays on screen
    t0, idx = 0.0, {"anime": 0, "games": 0}
    for e in entries:
        idx[e["kind"]] += 1
        e["no"] = idx[e["kind"]]
        e["tl"] = wrap(e["t"], int(inner / (22 * .72)))
        e["ml"] = wrap(e["m"], int(inner / (14 * .55)))
        e["nl"] = wrap(e["n"], int(inner / (17 * .53)))
        e["dur"] = round(max(7.0, min(16.0, 5 + .15 * len(e["n"].split()))), 1)
        e["start"], t0 = t0, t0 + e["dur"]
        y = 58                                   # first title baseline (relative to panel top)
        e["ty"] = [y + 30 * j for j in range(len(e["tl"]))]
        y = e["ty"][-1] + 16                     # rating tag top
        e["tagy"] = y
        y += 25 + 24                             # first meta baseline
        e["my"] = [y + 21 * j for j in range(len(e["ml"]))]
        y = e["my"][-1] + 36                     # first note baseline
        e["ny"] = [y + 27 * j for j in range(len(e["nl"]))]
        y = e["ny"][-1]
        e["sy"] = y + 34 if e.get("u") else None
        e["h"] = (e["sy"] or y) + PAD + 6
    tot = round(t0, 1)
    ph = max(max(e["h"] for e in entries), ROW_H * max(counts.values()))
    start = {"anime": 0.0, "games": sum(e["dur"] for e in entries if e["kind"] == "anime")}
    span = {k: sum(e["dur"] for e in entries if e["kind"] == k) for k in start}

    tab_w, tab_h = 112, 44
    ytab = y0
    ylist = ytab + tab_h + 24
    out = [hd]
    css = [f".lg,.tabo,.hl,.en{{opacity:0;}}.lg0,.tabo0,.hl0,.en0{{opacity:1;}}"]

    # tabs (outlined base + inverted overlay that lights up for the active tab)
    for k, (kind, label) in enumerate((("anime", "Anime"), ("games", "Games"))):
        x = 24 + k * (tab_w + 10)
        out.append(f'<g transform="translate({x},{ytab})">'
                   f'<rect x="1" y="1" width="{tab_w - 2}" height="{tab_h - 2}" fill="{pal["bg"]}" stroke="{pal["ink"]}" stroke-width="2"/>'
                   + t(tab_w / 2, 28, label, 17, pal["ink"], 700, "middle")
                   + f'<g class="tabo{" tabo0" if k == 0 else ""}" style="animation:tab_{kind} {tot}s infinite both">'
                     f'<rect width="{tab_w}" height="{tab_h}" fill="{pal["ink"]}"/>'
                   + t(tab_w / 2, 28, label, 17, pal["bg"], 700, "middle") + '</g></g>')
        css.append(win(f"tab_{kind}", start[kind], start[kind] + span[kind], tot, .4, "opacity:1", "opacity:0"))
        css.append(win(f"lg_{kind}", start[kind], start[kind] + span[kind], tot, .5, "opacity:1", "opacity:0"))

    # panel frame
    out.append(f'<rect x="{px}" y="{ylist}" width="{pw}" height="{ph}" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2"/>')

    # accordion rows: base row + inverted overlay while "open"
    for kind in ("anime", "games"):
        rows = []
        for r, e in enumerate([e for e in entries if e["kind"] == kind]):
            gi = entries.index(e)
            y = r * ROW_H
            title, rate = e["t"], e["r"]
            avail = 366                      # from the title's x (54) to the rating's right edge (420)
            tsz, rs = 15.5, 13.5

            def need():
                return tw(title, tsz, .54) + tw(rate, rs, .5) + 18

            while need() > avail and rs > 11:
                rs -= .5
            while need() > avail and tsz > 14:
                tsz -= .5
            while need() > avail and len(title) > 8:
                title = title[:-2].rstrip() + "…"
            ty = y + 33
            hot = pal["block"] if pal is LIGHT else LIGHT["accent"]   # readable on the inverted row
            rows.append(
                f'<g class="rw"><rect x="24" y="{y + ROW_H - 1}" width="{LIST_W}" height="1" fill="{pal["ink"]}"/>'
                f'<text class="disp" x="30" y="{ty}" font-size="15" fill="{pal["accent"]}">+</text>'
                + t(54, ty, title, tsz, pal["ink"], 700)
                + t(24 + LIST_W - 8, ty, rate, rs, pal["accent"], 700, "end")
                + f'</g><g class="hl{" hl0" if r == 0 else ""}" style="animation:hl{gi} {tot}s infinite both">'
                  f'<rect x="24" y="{y}" width="{LIST_W}" height="{ROW_H - 1}" fill="{pal["ink"]}"/>'
                  f'<text class="disp" x="30" y="{ty}" font-size="15" fill="{hot}">–</text>'
                + t(54, ty, title, tsz, pal["bg"], 700)
                + t(24 + LIST_W - 8, ty, rate, rs, hot, 700, "end") + '</g>')
            css.append(win(f"hl{gi}", e["start"], e["start"] + e["dur"], tot, .3, "opacity:1", "opacity:0"))
        out.append(f'<g transform="translate(0,{ylist})"><g class="lg{" lg0" if kind == "anime" else ""}" '
                   f'style="animation:lg_{kind} {tot}s infinite both">{"".join(rows)}</g></g>')

    # progress bar across the top of the panel (fills while one card is showing)
    stops = [(0, "transform:scaleX(0)")]
    for e in entries:
        a, b = e["start"] / tot * 100, (e["start"] + e["dur"]) / tot * 100
        if a > 0:
            stops.append((a, "transform:scaleX(0)"))
        stops.append((b - .001, "transform:scaleX(1)"))
    stops.append((100, "transform:scaleX(0)"))
    css.append(kf("prog", stops))
    css.append(f".pg{{transform-box:fill-box;transform-origin:left center;animation:prog {tot}s linear infinite both;}}")
    out.append(f'<rect class="pg" x="{px}" y="{ylist}" width="{pw}" height="5" fill="{pal["accent"]}"/>')

    # detail cards
    for gi, e in enumerate(entries):
        x = px + PAD
        k_ = [0]

        def ln(svg, gi=gi, e=e):
            """Wrap a line so it fades in a beat after the one above."""
            k = k_[0]
            k_[0] += 1
            return (f'<g class="ln" style="animation:l{gi} {tot}s {e["start"] + .25 + k * .07:.2f}s infinite both">{svg}</g>')

        cur = [ln(t(px + pw - PAD, ylist + 30, f'{e["kind"].upper()}  ·  {e["no"]} / {counts[e["kind"]]}',
                    12, pal["muted"], 700, "end", extra=' letter-spacing="1"'))]
        for l, yy in zip(e["tl"], e["ty"]):
            cur.append(ln(f'<text class="disp" x="{x}" y="{ylist + yy}" font-size="22" fill="{pal["accent"]}">{esc(l)}</text>'))
        rw = tw(e["r"], 14, .6) + 22
        cur.append(ln(f'<rect x="{x}" y="{ylist + e["tagy"]}" width="{rw}" height="25" fill="{pal["block"]}"/>'
                      + t(x + rw / 2, ylist + e["tagy"] + 18, e["r"], 14, pal["block_ink"], 700, "middle")))
        for l, yy in zip(e["ml"], e["my"]):
            cur.append(ln(t(x, ylist + yy, l, 14, pal["muted"])))
        for l, yy in zip(e["nl"], e["ny"]):
            cur.append(ln(t(x, ylist + yy, l, 17, pal["ink"])))
        if e.get("u"):
            cur.append(ln(t(x, ylist + e["sy"], "STEAM", 12, pal["accent"], 700, extra=' letter-spacing="1"')
                          + t(x + 62, ylist + e["sy"], steam_id(e["u"]), 12, pal["muted"], 400)))
        out.append(f'<g class="en{" en0" if gi == 0 else ""}" style="animation:en{gi} {tot}s infinite both">{"".join(cur)}</g>')
        css.append(win(f"en{gi}", e["start"], e["start"] + e["dur"], tot, .45,
                       "opacity:1;transform:none", "opacity:0;transform:translateX(18px)"))
        css.append(win(f"l{gi}", 0, e["dur"] + .3, tot, .4,
                       "opacity:1;transform:none", "opacity:0;transform:translateY(8px)"))
    css.append(".ln{opacity:1;}")
    return y0 + tab_h + 24 + ph + 56, "".join(out), "".join(css)


def sec_contact(d, pal):
    S = d["sections"]["contact"]
    hd, y0 = head(S["h2"], S["sub"], pal)
    label = html.unescape(d["contact_btn"].group(2))
    w = tw(label, 17, .6) + 44
    css = (win("ct_g", 0, 3, 6, .3, "transform:translateY(-3px) rotate(-1.5deg)", "transform:none")
           + win("ct_r", 0, 3, 6, .3, f'fill:{pal["accent"]}', f'fill:{pal["ink"]}')
           + ".ctg{transform-box:fill-box;transform-origin:center;animation:ct_g 6s infinite both;}"
             ".ctr{animation:ct_r 6s infinite both;}")
    btn = (f'<g transform="translate(24,{y0})"><g class="ctg">'
           f'<rect class="ctr" x="1" y="1" width="{w - 2}" height="46" fill="{pal["ink"]}"/>'
           + t(w / 2, 31, label, 17, pal["bg"], 700, "middle") + '</g></g>')
    return y0 + 48 + 60, hd + btn, css


def sec_stats(d, pal, prev):
    hd, y0 = head("GitHub stats", "Numbers refresh themselves every day.", pal)
    tile_w, th, gap, x0 = 204, 96, 12, 24
    tiles = [("Streak", "streak_data"), ("Stars", "star_data"), ("Repos", "repo_data"),
             ("Contribs", "contrib_data"), ("Commits", "commit_data"), ("Followers", "follower_data")]
    n, step = len(tiles) + 1, 1.4
    parts = []

    def val(i, default="0"):
        return prev.get(i, default)

    for i, (lab, tid) in enumerate(tiles):
        row, col = divmod(i, 4)
        x, y = x0 + col * (tile_w + gap), row * (th + gap)
        dl = f'style="animation-delay:{i * step:.1f}s"'
        parts.append(f'<g class="tl" {dl}>'
                     f'<rect class="tlr" x="{x}" y="{y}" width="{tile_w}" height="{th}" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2" {dl}/>'
                     + t(x + 16, y + 30, lab.upper(), 12, pal["muted"], 700, extra=' letter-spacing="1"')
                     + f'<text id="{tid}" class="disp" x="{x + 16}" y="{y + 70}" font-size="32" '
                       f'fill="{pal["accent"] if i % 2 else pal["ink"]}">{val(tid)}</text></g>')
    x, y, w, h = x0 + 2 * (tile_w + gap), th + gap, 2 * tile_w + gap, 120
    bar = w - 32
    dl = f'style="animation-delay:{len(tiles) * step:.1f}s"'
    parts.append(f'<g class="tl" {dl}>'
                 f'<rect class="tlr" x="{x}" y="{y}" width="{w}" height="{h}" fill="{pal["panel"]}" stroke="{pal["ink"]}" stroke-width="2" {dl}/>'
                 + t(x + 16, y + 30, "LINES OF CODE", 12, pal["muted"], 700, extra=' letter-spacing="1"')
                 + f'<text id="loc_data" class="disp" x="{x + 16}" y="{y + 70}" font-size="32" fill="{pal["ink"]}">{val("loc_data")}</text>'
                 + f'<rect x="{x + 16}" y="{y + 82}" width="{bar}" height="8" fill="{pal["bg"]}"/>'
                 + f'<rect id="loc_bar" x="{x + 16}" y="{y + 82}" width="{val("loc_bar", "0")}" height="8" fill="{pal["accent"]}" class="lb"/>'
                 + f'<text id="loc_add" x="{x + 16}" y="{y + 110}" font-size="12" font-weight="700" fill="{pal["add"]}">{val("loc_add", "++ 0")}</text>'
                 + f'<text id="loc_del" x="{x + w - 16}" y="{y + 110}" text-anchor="end" font-size="12" font-weight="700" fill="{pal["dele"]}">{val("loc_del", "-- 0")}</text></g>')
    tot = round(n * step, 1)
    css = (win("tl_g", 0, step, tot, .3, "transform:translateY(-4px)", "transform:none")
           + win("tl_r", 0, step, tot, .3, f'stroke:{pal["accent"]}', f'stroke:{pal["ink"]}')
           + f".tl{{animation:tl_g {tot}s infinite both;}}.tlr{{animation:tl_r {tot}s infinite both;}}"
           + kf("lb_g", [(0, "transform:scaleX(0)"), (4, "transform:scaleX(0)"), (20, "transform:scaleX(1)"),
                         (100, "transform:scaleX(1)")])
           + ".lb{transform-box:fill-box;transform-origin:left center;animation:lb_g 10s ease-out infinite both;}")
    return y0 + (th + gap) + h + 56, hd + f'<g transform="translate(0,{y0})">{"".join(parts)}</g>', css


def sec_footer(d, pal):
    h = 84
    body = (f'<rect x="24" y="0" width="{W - 48}" height="2" fill="{pal["ink"]}"/>'
            + t(24, 52, d["footer"][0], 17, pal["muted"])
            + t(W - 24, 52, d["footer"][1], 17, pal["muted"], anchor="end"))
    return h, body, ""


# --------------------------------------------------------------------------- #
# assemble one SVG per theme
# --------------------------------------------------------------------------- #
STAT_IDS = ["streak_data", "star_data", "repo_data", "contrib_data", "commit_data",
            "follower_data", "loc_data", "loc_add", "loc_del"]


def prev_stats():
    """Keep the numbers today.py wrote last time, so a rebuild never resets them to 0."""
    for name in ("profile_light.svg", "profile_dark.svg"):
        p = os.path.join(ASSETS, name)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        out = {}
        for i in STAT_IDS:
            m = re.search(r'<text\b[^>]*\bid="%s"[^>]*>(.*?)</text>' % i, s, re.S)
            if m:
                out[i] = m.group(1)
        m = re.search(r'<rect\b[^>]*\bid="loc_bar"[^>]*?\bwidth="([^"]*)"', s)
        if m:
            out["loc_bar"] = m.group(1)
        return out
    return {}


def build_svg(d, pal, fonts, prev):
    secs = [sec_nav(d, pal), sec_hero(d, pal), sec_buttons(d, pal), sec_marquee(d, pal),
            sec_projects(d, pal), sec_skills(d, pal), sec_log(d, pal), sec_contact(d, pal),
            sec_stats(d, pal, prev), sec_footer(d, pal)]
    y, body, css = 0, [], []
    for h, b, c in secs:
        body.append(f'<g transform="translate(0,{y})">{b}</g>')
        css.append(c)
        y += h
    label = f'{d["title"]} - {d["flash"]}'
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{y}" viewBox="0 0 {W} {y}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<style>
{fonts}
text{{font-family:{BODY};}}
.disp{{font-family:{DISPLAY};font-weight:400;}}
{"".join(css)}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;}}}}
</style>
<rect width="{W}" height="{y}" fill="{pal["bg"]}"/>
{"".join(body)}
</svg>
'''
    return y, svg


def build_readme(d, height):
    alt = (f'{d["title"]} - {d["flash"]} Projects: ' + ", ".join(p["name"] for p in d["projects"])
           + ". Tools: " + ", ".join(d["skills"]) + ". Logbook of anime and games with ratings.")
    return f'''<div align="center">

<picture>
<source media="(prefers-color-scheme: dark)" srcset="assets/profile_dark.svg">
<source media="(prefers-color-scheme: light)" srcset="assets/profile_light.svg">
<img src="assets/profile_light.svg" alt="{esc(alt)}" width="{W}">
</picture>

</div>
'''


def main():
    d = parse_source()
    print(f"parsed: {len(d['projects'])} projects, {len(d['skills'])} skills, "
          f"{len(d['anime'])} anime, {len(d['games'])} games")
    fonts = load_fonts()
    print("fonts embedded" if fonts else "fonts NOT embedded (fallback stack)")
    prev = prev_stats()
    os.makedirs(ASSETS, exist_ok=True)
    for f in os.listdir(ASSETS):  # drop the old per-part files
        if f.endswith(".svg"):
            os.remove(os.path.join(ASSETS, f))
    height = 0
    for theme, pal in (("light", LIGHT), ("dark", DARK)):
        height, svg = build_svg(d, pal, fonts, prev)
        with open(os.path.join(ASSETS, f"profile_{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    open(os.path.join(HERE, "README.md"), "w", encoding="utf-8").write(build_readme(d, height))
    print(f"wrote README.md and assets/profile_light.svg + profile_dark.svg ({W}x{height})")


if __name__ == "__main__":
    main()
