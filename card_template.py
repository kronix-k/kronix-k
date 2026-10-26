TEMPLATE = r'''<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="985" height="580" viewBox="0 0 985 580" fill="none">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&amp;family=Roboto+Mono:wght@500&amp;display=swap');
        .d-title { font: bold 32px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @title@; }
        .d-subtitle { font: 500 16px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @subtitle@; }
        .d-body-text { font: 400 14px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @body@; }
        .d-label { font: bold 12px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @label@; text-transform: uppercase; letter-spacing: 1px; }
        .d-mono { font: 500 14px 'Roboto Mono', 'Courier New', monospace; fill: @title@; }
        .d-stat-value { font: bold 64px 'Roboto Mono', 'Courier New', monospace; fill: @rank_val@; }
        .d-streak-value { font: bold 48px 'Roboto Mono', 'Courier New', monospace; fill: @streak_val@; }
        .d-chip-bg { fill: @chip@; stroke: @label@; stroke-width: 1; }
        .d-chip-bg-ide { fill: @chip_hi@; stroke: @label@; stroke-width: 1; }
        .d-chip-text { font: 500 12px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @chip_text@; }
        .d-add-color { fill: @add@; }
        .d-del-color { fill: @del@; }
    </style>

    <!-- Background -->
    <rect width="985" height="580" rx="28" fill="@bg@"/>

    <!-- Header Card -->
    <rect x="24" y="24" width="450" height="180" rx="24" fill="@card@"/>
    <circle cx="72" cy="72" r="32" fill="@avatar@"/>
    <text x="72" y="81" text-anchor="middle" style="font: bold 24px 'Inter', 'Segoe UI', Arial, sans-serif; fill: @avatar_text@;">KK</text>

    <text x="120" y="65" class="d-title">kronix-k</text>
    <text x="120" y="90" class="d-subtitle">Low-level systems &#183; Interactive UIs</text>
    <text x="50" y="135" class="d-body-text">Passionate about constant learning</text>

    <!-- Tool Chips -->
    <g transform="translate(50, 160)">
        <rect width="76" height="26" rx="8" class="d-chip-bg"/>
        <text x="12" y="17" class="d-chip-text">Android</text>
        <rect x="86" width="64" height="26" rx="8" class="d-chip-bg"/>
        <text x="98" y="17" class="d-chip-text">Kotlin</text>
        <rect x="160" width="54" height="26" rx="8" class="d-chip-bg"/>
        <text x="172" y="17" class="d-chip-text">Rust</text>
        <rect x="224" width="44" height="26" rx="8" class="d-chip-bg"/>
        <text x="236" y="17" class="d-chip-text">Go</text>
        <rect x="278" width="72" height="26" rx="8" class="d-chip-bg-ide"/>
        <text x="290" y="17" class="d-chip-text">Python</text>
    </g>

    <!-- Streak Card -->
    <rect x="494" y="24" width="220" height="180" rx="24" fill="@streak_bg@" stroke="@streak_stroke@" stroke-width="1"/>
    <text x="518" y="55" class="d-label" fill="@streak_val@">Current Streak</text>
    <text x="518" y="140" id="streak_data" class="d-streak-value">0</text>
    <text x="518" y="170" class="d-body-text" fill="@streak_val@" style="font-size: 12px; fill: @streak_val@;">Consecutive Days</text>

    <!-- Stars Card -->
    <rect x="734" y="24" width="227" height="180" rx="24" fill="@rank_bg@"/>
    <text x="754" y="55" class="d-label" style="fill: @rank_val@; fill-opacity: 0.7;">Stars Earned</text>
    <text x="754" y="140" id="star_data" class="d-stat-value" style="font-size: 54px;">0</text>
    <text x="754" y="170" class="d-body-text" style="font-size: 12px; fill: @rank_val@;">Across all repos</text>

    <!-- Tech Stack Card -->
    <rect x="24" y="224" width="550" height="260" rx="24" stroke="@label@" stroke-width="1"/>
    <text x="48" y="265" class="d-subtitle" style="font-size: 18px;">Tech Stack</text>

    <text x="48" y="295" class="d-label">Programming</text>
    <text x="48" y="315" class="d-body-text" style="fill: @title@;">Kotlin, Python, Rust, Go</text>

    <text x="48" y="355" class="d-label">Platforms &amp; Web</text>
    <text x="48" y="375" class="d-body-text" style="fill: @title@;">Android, Node.js, HTML5, CSS3</text>

    <text x="48" y="415" class="d-label">Currently Working On</text>
    <text x="48" y="435" class="d-body-text" style="fill: @title@;">Neo Assistant, CLI Calculator, Temp Converter, Warranty Manager</text>

    <!-- Git Metrics Cards -->
    <rect x="594" y="224" width="177" height="100" rx="24" fill="@card@"/>
    <text x="682" y="270" text-anchor="middle" id="repo_data" class="d-mono" style="font-size: 22px; font-weight: bold;">0</text>
    <text x="682" y="295" text-anchor="middle" class="d-label">Repos</text>

    <rect x="784" y="224" width="177" height="100" rx="24" fill="@card@"/>
    <text x="872" y="270" text-anchor="middle" id="contrib_data" class="d-mono" style="font-size: 22px; font-weight: bold; fill: @contrib@;">0</text>
    <text x="872" y="295" text-anchor="middle" class="d-label">Contribs</text>

    <!-- LOC Card -->
    <rect x="594" y="344" width="367" height="140" rx="24" fill="@card@"/>
    <text x="618" y="390" class="d-label">Total Lines of Code</text>
    <text x="943" y="390" text-anchor="end" id="loc_data" class="d-mono" style="font-size: 20px;">0</text>

    <rect x="618" y="410" width="319" height="12" rx="6" fill="@chip@"/>
    <rect id="loc_bar" x="618" y="410" width="0" height="12" rx="6" fill="@bar@"/>

    <text x="618" y="450" id="loc_add" class="d-mono d-add-color" style="font-size: 11px;">++ 0</text>
    <text x="943" y="450" text-anchor="end" id="loc_del" class="d-mono d-del-color" style="font-size: 11px;">-- 0</text>

    <!-- Footer -->
    <rect x="24" y="504" width="937" height="52" rx="16" fill="@chip@"/>
    <text x="48" y="535" class="d-body-text" style="font-size: 12px; font-weight: 500;">github.com/kronix-k | Followers: <tspan id="follower_data">0</tspan></text>
    <text x="940" y="535" text-anchor="end" id="commit_data" class="d-mono" style="font-size: 12px; fill-opacity: 0.6;">Commits: 0</text>
</svg>
'''
DARK = dict(bg="#1C1B1F", card="#332F37", title="#E6E1E5", subtitle="#D0BCFF", body="#CAC4D0",
    label="#938F99", rank_val="#EADDFF", rank_bg="#4F378B", streak_val="#BFCBAD", streak_bg="#2D332B",
    streak_stroke="#444C3E", chip="#49454F", chip_hi="#4F378B", chip_text="#CAC4D0", add="#81C784",
    **{"del":"#E57373"}, avatar="#D0BCFF", avatar_text="#381E72", contrib="#EFB8C8", bar="#D0BCFF")
LIGHT = dict(bg="#FFFBFE", card="#F3EDF7", title="#1C1B1F", subtitle="#6750A4", body="#49454F",
    label="#79747E", rank_val="#21005D", rank_bg="#EADDFF", streak_val="#3B5A2A", streak_bg="#E6EFD9",
    streak_stroke="#C5D2B4", chip="#E7E0EC", chip_hi="#D0BCFF", chip_text="#49454F", add="#2E7D32",
    **{"del":"#C62828"}, avatar="#6750A4", avatar_text="#FFFFFF", contrib="#8C4A60", bar="#6750A4")
import re


def render_top(pal):
    s = TEMPLATE
    for k, v in pal.items():
        s = s.replace(f"@{k}@", v)
    left = re.findall(r"@\w+@", s)
    assert not left, left
    return s


if __name__ == "__main__":
    for name, pal in (("dark_mode.svg", DARK), ("light_mode.svg", LIGHT)):
        open(name, "w", encoding="utf-8").write(render_top(pal))
    print("ok")
