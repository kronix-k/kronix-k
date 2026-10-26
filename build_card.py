#!/usr/bin/env python3
"""Build dark_mode.svg and light_mode.svg containing ALL profile content.

Reads content.md (anime, games, projects, fun facts, icons), downloads every
GIF/icon, shrinks the GIFs and embeds them as base64 data URIs, so the SVG is
fully self-contained (GitHub blocks external images inside SVGs).

Run:   pip install requests pillow && python build_card.py
Then:  python today.py   (fills in the live GitHub numbers)

Tunables (env vars): GIF_WIDTH (default 200), GIF_FRAMES (30), GIF_COLORS (64)
"""
import base64
import hashlib
import html
import io
import os
import re
import sys
import unicodedata

import requests

try:
    from PIL import Image
except ImportError:  # GIFs are then embedded unshrunk (can be very large)
    Image = None

from card_template import DARK, LIGHT, render_top

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
GIF_WIDTH = int(os.environ.get("GIF_WIDTH", 200))
GIF_FRAMES = int(os.environ.get("GIF_FRAMES", 30))
GIF_COLORS = int(os.environ.get("GIF_COLORS", 64))

HEADER_GIF = (
    "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExNGl5b2NtNzExZTJ2dmVscnRzaDdjZXg2MHcxbXQ0"
    "djVybnJ3cWdxNyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/GNPvfcYg0AxJYjDop6/giphy.gif"
)
FONT = "'Inter','Segoe UI',Arial,'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif"

CARD_W = 457          # width of a card in the 2-column grid
COL_X = (24, 504)     # x of the two columns
FULL_W = 937          # width of a full-width card
THUMB_W, THUMB_H = 156, 100


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape(s, quote=False)


def plain(s):
    return re.sub(r"\*+", "", s).strip()


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def units(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def wrap(text, limit):
    """Greedy word wrap using display units (CJK/emoji count double)."""
    lines = []
    for para in text.split("\n"):
        cur = ""
        for tok in re.findall(r"\S+\s*", para) or [""]:
            word = tok.rstrip()
            while units(word) > limit:  # unbreakable long token -> split by char
                cut, acc = 0, 0
                for ch in word:
                    w = units(ch)
                    if acc + w > limit:
                        break
                    acc += w
                    cut += 1
                if cur:
                    lines.append(cur.rstrip())
                    cur = ""
                lines.append(word[:cut])
                word = word[cut:]
                tok = word
            if units(cur + tok.rstrip()) > limit and cur:
                lines.append(cur.rstrip())
                cur = ""
            cur += tok
        lines.append(cur.rstrip())
    return lines


def fetch(url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest())
    if os.path.exists(path):
        return open(path, "rb").read()
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not download {url[:70]}...: {e}", file=sys.stderr)
        return None
    open(path, "wb").write(r.content)
    return r.content


def shrink_gif(raw, width, bg_hex):
    im = Image.open(io.BytesIO(raw))
    n = getattr(im, "n_frames", 1)
    step = max(1, -(-n // GIF_FRAMES))
    frames, durations = [], []
    bg = hex_rgb(bg_hex) + (255,)
    for i in range(0, n, step):
        im.seek(i)
        fr = im.convert("RGBA")
        if fr.width > width:
            fr = fr.resize((width, max(1, round(fr.height * width / fr.width))), Image.LANCZOS)
        base = Image.new("RGBA", fr.size, bg)
        base.alpha_composite(fr)
        frames.append(base.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=GIF_COLORS))
        durations.append(max(20, (im.info.get("duration") or 100) * step))
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True, disposal=1)
    return buf.getvalue()


def data_uri(url, bg_hex, width=None):
    """Download `url` and return a data: URI (GIFs are shrunk), or None."""
    raw = fetch(url)
    if raw is None:
        return None
    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    if ext == "gif" or raw[:3] == b"GIF":
        if Image is not None:
            try:
                raw = shrink_gif(raw, width or GIF_WIDTH, bg_hex)
            except Exception as e:  # noqa: BLE001
                print(f"  ! could not shrink gif, using original: {e}", file=sys.stderr)
        mime = "image/gif"
    elif ext == "svg":
        mime = "image/svg+xml"
    elif ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


# --------------------------------------------------------------------------- #
# content parsing (content.md)
# --------------------------------------------------------------------------- #
def parse_content(md):
    games_at = md.index("## 🎮")
    entries = []
    for m in re.finditer(r"<details>(.*?)</details>", md, re.S):
        blk = m.group(1)
        title = plain(re.search(r"<strong>(.*?)</strong>", blk).group(1))
        img = re.search(r'<img src="([^"]+)"', blk).group(1)
        meta = []
        for label, value in re.findall(r"^\|\s*(?:\*\*(.+?)\*\*)?\s*\|\s*(.*?)\s*\|\s*$", blk, re.M):
            if not value or set(value) <= set("-: "):
                continue
            if label:
                meta.append([label, plain(value)])
            elif meta:  # continuation row (e.g. romanisation)
                meta[-1][1] += "\n" + plain(value)
        body = " ".join(
            l.strip() for l in blk.splitlines()
            if l.strip() and not l.lstrip().startswith(("<", "|", "🔗"))
        )
        steam = re.search(r"\[View on Steam\]\((.*?)\)", blk)
        entries.append({
            "kind": "game" if m.start() > games_at else "anime",
            "title": title, "img": img, "meta": meta, "body": plain(body),
            "steam": steam.group(1) if steam else None,
        })

    def section(start, end="\n---"):
        i = md.index(start)
        j = md.find(end, i + len(start))
        return md[i:j if j != -1 else len(md)]

    icons = re.findall(r'<img src="([^"]+)" alt="([^"]+)"', section("## 🛠"))
    projects = [(plain(a), plain(b)) for a, b in
                re.findall(r"^\| (.+?) \| (.+?) \|$", section("## 🔭"), re.M)
                if not a.startswith(("Project", "---"))]
    facts = [plain(l[2:]) for l in section("## ⚡").splitlines() if l.startswith("- ")]
    footer = re.findall(r'<img src="([^"]+)" alt="Yotsugi GIF"', md)
    return {
        "entries": entries, "icons": icons, "projects": projects, "facts": facts,
        "footer_gif": footer[0] if footer else None,
    }


# --------------------------------------------------------------------------- #
# svg builder
# --------------------------------------------------------------------------- #
class Canvas:
    def __init__(self, pal, tag):
        self.pal, self.tag, self.parts, self.y, self.n = pal, tag, [], 580, 0

    def text(self, x, y, s, size=13, fill=None, weight=400, anchor=None, extra=""):
        a = f' text-anchor="{anchor}"' if anchor else ""
        self.parts.append(
            f'<text x="{x}" y="{y}"{a} style="font-family:{FONT};font-size:{size}px;'
            f'font-weight:{weight};fill:{fill or self.pal["body"]};{extra}">{esc(s)}</text>')

    def rect(self, x, y, w, h, r=24, fill=None, stroke=None):
        st = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or "none"}"{st}/>')

    def image(self, x, y, w, h, uri, r=12):
        if uri is None:
            self.rect(x, y, w, h, r, fill=self.pal["chip"])
            self.text(x + w / 2, y + h / 2 + 4, "image unavailable", 11, self.pal["label"], anchor="middle")
            return
        self.n += 1
        cid = f"{self.tag}c{self.n}"
        self.parts.append(
            f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/></clipPath>'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" href="{uri}" '
            f'preserveAspectRatio="xMidYMid meet" clip-path="url(#{cid})"/>')

    def heading(self, s):
        self.text(24, self.y + 26, s, 20, self.pal["subtitle"], 700)
        self.y += 46

    def grid(self, cards):
        """Lay out cards two per row; both cards in a row share the same height."""
        for i in range(0, len(cards), 2):
            row = cards[i:i + 2]
            h = max(c["h"] for c in row)
            for col, c in enumerate(row):
                c["draw"](COL_X[col], self.y, h)
            self.y += h + 20


def entry_card(cv, e, bg_hex):
    pal = cv.pal
    pad = 18
    title_lines = wrap(e["title"], 50)
    meta_x = pad + THUMB_W + 14
    meta_lines = []  # (label or None, text)
    for label, value in e["meta"]:
        ls = wrap(f"{label}: {value}", 38)
        meta_lines.append((label, ls))
    meta_h = sum(len(ls) for _, ls in meta_lines) * 16
    block_h = max(THUMB_H, meta_h)
    body_lines = wrap(e["body"], 58)
    title_h = 18 * len(title_lines)
    h = 22 + title_h + 10 + block_h + 16 + 18 * len(body_lines) + 18

    uri = data_uri(e["img"], bg_hex, GIF_WIDTH)

    def draw(x, y, hh):
        cv.rect(x, y, CARD_W, hh, 24, fill=pal["card"])
        ty = y + 28
        for ln in title_lines:
            cv.text(x + pad, ty, ln, 15, pal["title"], 700)
            ty += 18
        by = ty - 8
        cv.image(x + pad, by, THUMB_W, THUMB_H, uri)
        my = by + 12
        for label, ls in meta_lines:
            for k, ln in enumerate(ls):
                if k == 0:
                    rest = ln[len(label) + 2:]
                    cv.parts.append(
                        f'<text x="{x + meta_x}" y="{my}" style="font-family:{FONT};font-size:12px;">'
                        f'<tspan style="font-weight:700;fill:{pal["label"]}">{esc(label)}: </tspan>'
                        f'<tspan style="fill:{pal["title"]}">{esc(rest)}</tspan></text>')
                else:
                    cv.text(x + meta_x, my, ln, 12, pal["title"])
                my += 16
        py = by + block_h + 24
        for ln in body_lines:
            cv.text(x + pad, py, ln, 13, pal["body"])
            py += 18
        if e["steam"]:
            cv.text(x + CARD_W - pad, y + hh - 10, "store.steampowered.com", 10, pal["label"], anchor="end")

    return {"h": h, "draw": draw}


def project_card(cv, name, desc):
    pal = cv.pal
    lines = wrap(desc, 58)
    h = 24 + 20 + 18 * len(lines) + 18

    def draw(x, y, hh):
        cv.rect(x, y, CARD_W, hh, 24, fill=pal["card"])
        cv.text(x + 20, y + 32, name, 15, pal["title"], 700)
        yy = y + 56
        for ln in lines:
            cv.text(x + 20, yy, ln, 13, pal["body"])
            yy += 18

    return {"h": h, "draw": draw}


def banner(cv, url, bg_hex, height=220, width=400):
    cv.rect(24, cv.y, FULL_W, height + 20, 24, fill=cv.pal["card"])
    cv.image(24, cv.y + 10, FULL_W, height, data_uri(url, bg_hex, width), r=16)
    cv.y += height + 40


def build(pal, tag, content):
    cv = Canvas(pal, tag)
    bg = pal["card"]

    if True:  # header gif
        banner(cv, HEADER_GIF, bg)

    # Languages & tools
    cv.heading("🛠 Languages & Tools")
    cv.rect(24, cv.y, FULL_W, 96, 24, fill=pal["card"])
    slot = FULL_W / max(1, len(content["icons"]))
    for i, (url, alt) in enumerate(content["icons"]):
        cx = 24 + slot * i + slot / 2
        uri = data_uri(url, bg)
        if uri:
            cv.parts.append(f'<image x="{cx - 20:.1f}" y="{cv.y + 14}" width="40" height="40" href="{uri}"/>')
        cv.text(round(cx, 1), cv.y + 76, alt, 12, pal["body"], anchor="middle")
    cv.y += 96 + 20

    cv.heading("🔭 Currently Working On")
    cv.grid([project_card(cv, n, d) for n, d in content["projects"]])

    cv.heading("⚡ Fun Facts")
    lines = [wrap(f, 120) for f in content["facts"]]
    h = 24 + sum(len(l) for l in lines) * 22 + 6
    cv.rect(24, cv.y, FULL_W, h, 24, fill=pal["card"])
    yy = cv.y + 36
    for ls in lines:
        for ln in ls:
            cv.text(48, yy, ln, 14, pal["title"])
            yy += 22
    cv.y += h + 20

    cv.heading("📺 Anime I've Watched")
    cv.grid([entry_card(cv, e, bg) for e in content["entries"] if e["kind"] == "anime"])

    cv.heading("🎮 Games I've Played")
    cv.grid([entry_card(cv, e, bg) for e in content["entries"] if e["kind"] == "game"])

    if content["footer_gif"]:
        banner(cv, content["footer_gif"], bg)

    total_h = cv.y + 4
    top = render_top(pal).rstrip()
    assert top.endswith("</svg>")
    top = top[: -len("</svg>")]
    top = top.replace('height="580" viewBox="0 0 985 580"', f'height="{total_h}" viewBox="0 0 985 {total_h}"', 1)
    top = top.replace('<rect width="985" height="580" rx="28"', f'<rect width="985" height="{total_h}" rx="28"', 1)
    return top + "\n    <!-- Extended content -->\n    " + "\n    ".join(cv.parts) + "\n</svg>\n"


def main():
    content = parse_content(open(os.path.join(HERE, "content.md"), encoding="utf-8").read())
    print(f"parsed: {len(content['entries'])} entries, {len(content['icons'])} icons, "
          f"{len(content['projects'])} projects, {len(content['facts'])} facts")
    if Image is None:
        print("warning: Pillow not installed, GIFs will not be shrunk", file=sys.stderr)
    for name, pal, tag in (("dark_mode.svg", DARK, "d"), ("light_mode.svg", LIGHT, "l")):
        svg = build(pal, tag, content)
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {name}: {len(svg) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
