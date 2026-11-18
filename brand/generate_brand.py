#!/usr/bin/env python3
"""Memoir 品牌视觉资产生成器 — 原创 Memory Fold 符号 + 全变体 + 展示板。

颜色系统（Quiet Heritage）:
  Archive Ink    #263841
  Midnight Archive #192A33
  Memory Ivory   #F5F0E7
  Memory Amber   #B77B50
  Quiet Sage     #85958A
  Stone Mist     #CFC9BE
"""
from pathlib import Path

import cairosvg

OUT = Path(__file__).parent
INK = "#263841"
DARK = "#192A33"
IVORY = "#F5F0E7"
AMBER = "#B77B50"
SAGE = "#85958A"
STONE = "#CFC9BE"
SERIF = "Georgia, 'Noto Serif CJK SC', serif"
SANS = "Helvetica, Arial, sans-serif"

# ---------------- 原创 Memory Fold 符号 ----------------
# 两组对称折页构成 M 轮廓，中间负空间为连续记忆路径，琥珀节点为珍贵瞬间。
# 坐标系 0 0 200 200，背景透明。
def symbol_nodes(color=INK, accent=AMBER, path_color=SAGE):
    """返回组成符号的 SVG 图元字符串（不含 <svg> 包裹）。"""
    return f'''
  <!-- 左折页：从底向上翻折的一页档案 -->
  <path d="M28 172 V44 C28 38 33 34 39 34 H63 C69 34 74 38 76 44 L100 116 L76 124 L60 62 C59 58 55 56 51 56 H49 C45 56 42 59 42 63 V172 Z" fill="{color}"/>
  <!-- 右折页：镜像 -->
  <path d="M172 172 V44 C172 38 167 34 161 34 H137 C131 34 126 38 124 44 L100 116 L124 124 L140 62 C141 58 145 56 149 56 H151 C155 56 158 59 158 63 V172 Z" fill="{color}"/>
  <!-- 负空间：连续记忆路径（细线，连接左右折页顶部到底部中心） -->
  <path d="M50 50 C50 96 100 100 100 132 C100 100 150 96 150 50" fill="none" stroke="{path_color}" stroke-width="2.4" stroke-linecap="round" opacity="0.9"/>
  <!-- 底部路径延伸：时间轴 -->
  <path d="M100 132 V172" stroke="{path_color}" stroke-width="2.4" stroke-linecap="round" opacity="0.9"/>
  <!-- 记忆节点：珍贵瞬间 -->
  <circle cx="100" cy="132" r="7.5" fill="{accent}"/>
  <circle cx="100" cy="132" r="13" fill="none" stroke="{accent}" stroke-width="1.6" opacity="0.45"/>
'''


def svg_wrap(body, w, h, bg="none"):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">' + (
        f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg != "none" else ""
    ) + body + "</svg>"


def save_svg(name, content):
    (OUT / name).write_text(content, encoding="utf-8")


def render_png(svg_name, png_name, scale=1):
    cairosvg.svg2png(url=str(OUT / svg_name), write_to=str(OUT / png_name), scale=scale)


# ---- A. Symbol Logo（透明底，独立图形，用于 favicon / 头像）----
symbol = svg_wrap(symbol_nodes(), 200, 200)
save_svg("logo-symbol.svg", symbol)
render_png("logo-symbol.svg", "logo-symbol.png", scale=3)

# ---- B. Primary Logo（横向：图形 + 字标 + 副标题）----
primary = svg_wrap(f'''
  <g transform="translate(8,18) scale(0.82)">{symbol_nodes()}</g>
  <text x="188" y="86" font-family="{SERIF}" font-size="56" fill="{INK}">Memoir</text>
  <text x="190" y="118" font-family="{SANS}" font-size="11.5" letter-spacing="2.1" fill="{SAGE}">AI-POWERED LIFE STORY &amp; FAMILY MEMORY PLATFORM</text>
''', 660, 150)
save_svg("logo-primary.svg", primary)
render_png("logo-primary.svg", "logo-primary.png", scale=2)

# ---- C. Stacked Logo（纵向：图形 + 字标 + 口号）----
stacked = svg_wrap(f'''
  <g transform="translate(96,10) scale(1.02)">{symbol_nodes()}</g>
  <text x="200" y="278" text-anchor="middle" font-family="{SERIF}" font-size="54" fill="{INK}">Memoir</text>
  <text x="200" y="316" text-anchor="middle" font-family="{SANS}" font-size="14" letter-spacing="1.2" fill="{SAGE}">Your Life. Your Stories. Your Legacy.</text>
''', 400, 350)
save_svg("logo-stacked.svg", stacked)
render_png("logo-stacked.svg", "logo-stacked.png", scale=2)

# ---- D. Dark Version（深夜档案背景 + 纸白图形 + 琥珀节点）----
dark = svg_wrap(f'''
  <g transform="translate(8,18) scale(0.82)">{symbol_nodes(IVORY, AMBER, STONE)}</g>
  <text x="188" y="86" font-family="{SERIF}" font-size="56" fill="{IVORY}">Memoir</text>
  <text x="190" y="118" font-family="{SANS}" font-size="11.5" letter-spacing="2.1" fill="{STONE}">AI-POWERED LIFE STORY &amp; FAMILY MEMORY PLATFORM</text>
''', 660, 150, bg=DARK)
save_svg("logo-dark.svg", dark)
render_png("logo-dark.svg", "logo-dark.png", scale=2)

# ---- E. Monochrome（纯黑）----
mono = svg_wrap(f'''
  <g transform="translate(8,18) scale(0.82)">{symbol_nodes("#111111", "#111111", "#111111")}</g>
  <text x="188" y="86" font-family="{SERIF}" font-size="56" fill="#111111">Memoir</text>
  <text x="190" y="118" font-family="{SANS}" font-size="11.5" letter-spacing="2.1" fill="#111111">AI-POWERED LIFE STORY &amp; FAMILY MEMORY PLATFORM</text>
''', 660, 150)
save_svg("logo-monochrome.svg", mono)
render_png("logo-monochrome.svg", "logo-monochrome.png", scale=2)

# ---- F. App Icon（1:1 圆角方形 + 独立符号）----
appicon = svg_wrap(f'''
  <rect x="6" y="6" width="388" height="388" rx="84" fill="{DARK}"/>
  <g transform="translate(103,103) scale(1.82)">{symbol_nodes(IVORY, AMBER, STONE)}</g>
''', 400, 400)
save_svg("app-icon.svg", appicon)
render_png("app-icon.svg", "app-icon.png", scale=2)
# 多尺寸 favicon
for s in (16, 32, 64, 128, 192, 512):
    cairosvg.svg2png(url=str(OUT / "app-icon.svg"), write_to=str(OUT / f"favicon-{s}.png"), output_width=s, output_height=s)

# ---- G. README Banner（深蓝底，纸白字，琥珀点缀）----
banner = svg_wrap(f'''
  <defs>
    <pattern id="pf" width="64" height="64" patternUnits="userSpaceOnUse">
      <path d="M0 32 Q16 16 32 32 T64 32" fill="none" stroke="{SAGE}" stroke-width="1" opacity="0.10"/>
      <circle cx="32" cy="32" r="2" fill="{AMBER}" opacity="0.18"/>
    </pattern>
  </defs>
  <rect width="1280" height="420" fill="{DARK}"/>
  <rect width="1280" height="420" fill="url(#pf)"/>
  <g transform="translate(64,84) scale(1.5)">{symbol_nodes(IVORY, AMBER, STONE)}</g>
  <text x="404" y="196" font-family="{SERIF}" font-size="82" fill="{IVORY}">Memoir</text>
  <text x="408" y="234" font-family="{SANS}" font-size="14" letter-spacing="3" fill="{AMBER}">QUIET HERITAGE · AI-POWERED LIFE STORY PLATFORM</text>
  <text x="406" y="312" font-family="{SERIF}" font-size="30" fill="{STONE}">Your Life. Your Stories. Your Legacy.</text>
''', 1280, 420)
save_svg("banner.svg", banner)
render_png("banner.svg", "banner.png", scale=1)

# ---- H. 品牌 VI 展示板（16:9，精确排版）----
def swatch(x, y, w, h, color, label, hexv, light_text=False):
    fg = IVORY if light_text else INK
    return f'''
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{color}" stroke="{STONE}" stroke-width="1"/>
  <text x="{x+14}" y="{y+h-42}" font-family="{SANS}" font-size="15" fill="{fg}">{label}</text>
  <text x="{x+14}" y="{y+h-18}" font-family="{SANS}" font-size="13" fill="{fg}" opacity="0.75">{hexv}</text>'''

board = svg_wrap(f'''
  <rect width="1600" height="900" fill="{IVORY}"/>
  <text x="72" y="86" font-family="{SERIF}" font-size="46" fill="{INK}">Memoir</text>
  <text x="72" y="118" font-family="{SANS}" font-size="13" letter-spacing="2.6" fill="{SAGE}">BRAND VISUAL IDENTITY · QUIET HERITAGE · 静谧传承</text>
  <line x1="72" y1="140" x2="1528" y2="140" stroke="{STONE}" stroke-width="1.5"/>

  <text x="72" y="188" font-family="{SANS}" font-size="13" letter-spacing="2" fill="{AMBER}">01 · SYMBOL &amp; LOGO</text>
  <g transform="translate(72,215) scale(1.5)">{symbol_nodes()}</g>
  <rect x="250" y="244" width="640" height="150" rx="10" fill="none" stroke="{STONE}"/>
  <g transform="translate(266,258) scale(0.7)">{symbol_nodes()}</g>
  <text x="440" y="322" font-family="{SERIF}" font-size="46" fill="{INK}">Memoir</text>
  <text x="442" y="352" font-family="{SANS}" font-size="11" letter-spacing="2" fill="{SAGE}">AI-POWERED LIFE STORY &amp; FAMILY MEMORY PLATFORM</text>
  <rect x="250" y="410" width="640" height="150" rx="10" fill="{DARK}"/>
  <g transform="translate(266,424) scale(0.7)">{symbol_nodes(IVORY, AMBER, STONE)}</g>
  <text x="440" y="488" font-family="{SERIF}" font-size="46" fill="{IVORY}">Memoir</text>
  <text x="442" y="518" font-family="{SANS}" font-size="11" letter-spacing="2" fill="{STONE}">Your Life. Your Stories. Your Legacy.</text>

  <text x="960" y="188" font-family="{SANS}" font-size="13" letter-spacing="2" fill="{AMBER}">02 · COLOR SYSTEM</text>
  {swatch(960, 210, 176, 104, INK, 'Archive Ink', '#263841', True)}
  {swatch(1150, 210, 176, 104, DARK, 'Midnight Archive', '#192A33', True)}
  {swatch(1340, 210, 176, 104, IVORY, 'Memory Ivory', '#F5F0E7', False)}
  {swatch(960, 330, 176, 104, AMBER, 'Memory Amber', '#B77B50', True)}
  {swatch(1150, 330, 176, 104, SAGE, 'Quiet Sage', '#85958A', True)}
  {swatch(1340, 330, 176, 104, STONE, 'Stone Mist', '#CFC9BE', False)}

  <text x="72" y="620" font-family="{SANS}" font-size="13" letter-spacing="2" fill="{AMBER}">03 · TYPOGRAPHY</text>
  <text x="72" y="684" font-family="{SERIF}" font-size="54" fill="{INK}">Memoir — A Life Remembered</text>
  <text x="72" y="724" font-family="{SANS}" font-size="18" fill="{SAGE}">数字人生回忆录 · Your Life. Your Stories. Your Legacy.</text>

  <text x="72" y="800" font-family="{SANS}" font-size="13" letter-spacing="2" fill="{AMBER}">04 · MEMORY PATTERN &amp; TIMELINE</text>
  <path d="M72 860 Q160 820 240 860 T400 860 T560 860 T720 860 T880 860" fill="none" stroke="{INK}" stroke-width="2" opacity="0.45"/>
  <circle cx="240" cy="860" r="6" fill="{AMBER}"/>
  <circle cx="560" cy="860" r="6" fill="{AMBER}"/>
  <circle cx="880" cy="860" r="6" fill="{AMBER}"/>
  <text x="1280" y="820" font-family="{SANS}" font-size="18" fill="{SAGE}">Memory Fragments  ›  Life Stories  ›  Timeless Archive</text>
  <g transform="translate(1280,840) scale(0.55)">{symbol_nodes()}</g>
''', 1600, 900)
save_svg("brand-board.svg", board)
render_png("brand-board.svg", "brand-board.png", scale=1)

print("brand assets generated in", OUT)
for p in sorted(OUT.iterdir()):
    if p.is_file():
        print(f"  {p.name:28} {p.stat().st_size:>9} bytes")
