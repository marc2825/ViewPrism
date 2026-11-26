"""Generate the ViewPrism logo set (SVG is the source) and render PNGs with a headless browser.

    python tools/make_logo.py [--browser "<path to msedge.exe or chrome.exe>"]

Concept: the current view (viewfinder frame + white beam) passes through a prism and splits into
the four passes: depth (white -> grey, near = white), normal (blue-violet, normal-map colours),
object ID (coloured segments) and mask (mint).
"""
import argparse
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'branding'

BG_TOP, BG_BOTTOM = '#2a3246', '#141823'
INK = '#eef2f9'
PRISM_TOP, PRISM_BOTTOM = '#4a5976', '#283146'
DEPTH = ('#ffffff', '#6b7488')
NORMAL = ('#7d9bff', '#b48cff')
ID_SEGMENTS = ('#ff8f70', '#ffd166', '#5fd3c6')
MASK = '#7ce6b0'
FONT = "'Segoe UI Variable Display','Segoe UI','Inter','Helvetica Neue',Arial,sans-serif"

# Prism (equilateral, apex up) and beam geometry in a 512 x 512 box.
APEX, LEFT, RIGHT = (236.0, 128.0), (122.0, 325.0), (350.0, 325.0)


def on_edge(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def beam_entry(y):
    t = (LEFT[1] - y) / (LEFT[1] - APEX[1])
    return on_edge(LEFT, APEX, t)


def defs(small=False):
    rays = []
    starts = [on_edge(APEX, RIGHT, t) for t in (0.58, 0.67, 0.76, 0.85)]
    if small:
        ends = [(436.0, 160.0), (450.0, 230.0), (450.0, 302.0), (436.0, 372.0)]
    else:
        ends = [(426.0, 170.0), (440.0, 234.0), (440.0, 300.0), (426.0, 364.0)]
    for i, (s, e) in enumerate(zip(starts, ends)):
        rays.append((s, e))
    grads = f'''
    <linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>
    </linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{PRISM_TOP}"/><stop offset="1" stop-color="{PRISM_BOTTOM}"/>
    </linearGradient>
    <linearGradient id="wedge" gradientUnits="userSpaceOnUse" x1="{beam_entry(262)[0]:.1f}" y1="0" x2="{starts[2][0]:.1f}" y2="0">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.85"/><stop offset="1" stop-color="#ffffff" stop-opacity="0.18"/>
    </linearGradient>
    <linearGradient id="depth" gradientUnits="userSpaceOnUse" x1="{rays[0][0][0]:.1f}" y1="{rays[0][0][1]:.1f}" x2="{rays[0][1][0]:.1f}" y2="{rays[0][1][1]:.1f}">
      <stop offset="0" stop-color="{DEPTH[0]}"/><stop offset="1" stop-color="{DEPTH[1]}"/>
    </linearGradient>
    <linearGradient id="normal" gradientUnits="userSpaceOnUse" x1="{rays[1][0][0]:.1f}" y1="{rays[1][0][1]:.1f}" x2="{rays[1][1][0]:.1f}" y2="{rays[1][1][1]:.1f}">
      <stop offset="0" stop-color="{NORMAL[0]}"/><stop offset="1" stop-color="{NORMAL[1]}"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="7"/>
    </filter>'''
    return grads, rays


def ray_paths(rays, width, small=False):
    (d0, d1), (n0, n1), (i0, i1), (m0, m1) = rays
    out = [f'<line x1="{d0[0]:.1f}" y1="{d0[1]:.1f}" x2="{d1[0]:.1f}" y2="{d1[1]:.1f}" stroke="url(#depth)"/>',
           f'<line x1="{n0[0]:.1f}" y1="{n0[1]:.1f}" x2="{n1[0]:.1f}" y2="{n1[1]:.1f}" stroke="url(#normal)"/>']
    if small:
        out.append(f'<line x1="{i0[0]:.1f}" y1="{i0[1]:.1f}" x2="{i1[0]:.1f}" y2="{i1[1]:.1f}" stroke="{ID_SEGMENTS[1]}"/>')
    else:
        # object ID: three coloured segments with small gaps (distinct ids)
        n = len(ID_SEGMENTS)
        gap = 0.07
        for k, col in enumerate(ID_SEGMENTS):
            a = 0.10 + 0.90 * k / n + (gap / 2 if k else 0)          # start clear of the prism outline
            b = 0.10 + 0.90 * (k + 1) / n - (gap / 2 if k < n - 1 else 0)
            p = (i0[0] + (i1[0] - i0[0]) * a, i0[1] + (i1[1] - i0[1]) * a)
            q = (i0[0] + (i1[0] - i0[0]) * b, i0[1] + (i1[1] - i0[1]) * b)
            out.append(f'<line x1="{p[0]:.1f}" y1="{p[1]:.1f}" x2="{q[0]:.1f}" y2="{q[1]:.1f}" stroke="{col}"/>')
    out.append(f'<line x1="{m0[0]:.1f}" y1="{m0[1]:.1f}" x2="{m1[0]:.1f}" y2="{m1[1]:.1f}" stroke="{MASK}"/>')
    return f'<g stroke-width="{width}" stroke-linecap="round" fill="none">' + ''.join(out) + '</g>'


def icon_body(small=False):
    grads, rays = defs(small)
    beam_y = 262.0
    entry = beam_entry(beam_y)
    exit_mid = on_edge(APEX, RIGHT, 0.715)
    stroke = 22 if small else 14
    ray_w = 26 if small else 18
    parts = [f'<defs>{grads}</defs>',
             '<rect x="8" y="8" width="496" height="496" rx="116" fill="url(#bg)"/>',
             '<rect x="9" y="9" width="494" height="494" rx="115" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="2"/>']
    if not small:
        # viewfinder corners: "captured from the view"
        c, ln, i = 62, 54, 58
        corners = [(i, i, 1, 1), (512 - i, i, -1, 1), (i, 512 - i, 1, -1), (512 - i, 512 - i, -1, -1)]
        for x, y, sx, sy in corners:
            parts.append(f'<path d="M{x} {y + sy * ln} V{y} H{x + sx * ln}" fill="none" stroke="{INK}" '
                         f'stroke-opacity="0.32" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>')
        del c
    # input beam (the view)
    x0 = 70.0 if not small else 54.0
    parts.append(f'<line x1="{x0}" y1="{beam_y}" x2="{entry[0]:.1f}" y2="{beam_y}" stroke="{INK}" '
                 f'stroke-width="{ray_w}" stroke-linecap="round"/>')
    # glow behind the passes
    parts.append(f'<g filter="url(#glow)" opacity="0.55">{ray_paths(rays, ray_w + 6, small)}</g>')
    # prism body
    tri = f'M{APEX[0]} {APEX[1]} L{RIGHT[0]} {RIGHT[1]} L{LEFT[0]} {LEFT[1]} Z'
    parts.append(f'<path d="{tri}" fill="url(#glass)"/>')
    # refracted light inside the prism (widening wedge)
    if not small:
        parts.append(f'<path d="M{entry[0]:.1f} {beam_y - 4} L{exit_mid[0]:.1f} {exit_mid[1] - 26:.1f} '
                     f'L{exit_mid[0]:.1f} {exit_mid[1] + 26:.1f} L{entry[0]:.1f} {beam_y + 4} Z" fill="url(#wedge)"/>')
        # glass highlight along the left face
        hl0, hl1 = on_edge(LEFT, APEX, 0.55), on_edge(LEFT, APEX, 0.86)
        parts.append(f'<line x1="{hl0[0] + 16:.1f}" y1="{hl0[1] + 2:.1f}" x2="{hl1[0] + 10:.1f}" y2="{hl1[1] + 6:.1f}" '
                     f'stroke="#ffffff" stroke-opacity="0.22" stroke-width="7" stroke-linecap="round"/>')
    # passes
    parts.append(ray_paths(rays, ray_w, small))
    # prism outline on top
    parts.append(f'<path d="{tri}" fill="none" stroke="{INK}" stroke-width="{stroke}" stroke-linejoin="round"/>')
    return '\n  '.join(parts)


def icon_svg(small=False, size=512):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 512 512">\n'
            f'  <title>ViewPrism</title>\n  {icon_body(small)}\n</svg>\n')


def wordmark_svg(theme):
    text = '#151a24' if theme == 'light' else '#f2f5fb'
    sub = '#5c6577' if theme == 'light' else '#9aa4b8'
    body = icon_body(False).replace('id="', 'id="w').replace('url(#', 'url(#w')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1480" height="400" viewBox="0 0 1480 400">
  <title>ViewPrism - Viewport Pass Exporter</title>
  <defs>
    <linearGradient id="spectrum" gradientUnits="userSpaceOnUse" x1="740" y1="0" x2="1115" y2="0">
      <stop offset="0" stop-color="{NORMAL[0]}"/><stop offset="0.28" stop-color="{NORMAL[1]}"/>
      <stop offset="0.55" stop-color="{ID_SEGMENTS[0]}"/><stop offset="0.8" stop-color="{ID_SEGMENTS[1]}"/>
      <stop offset="1" stop-color="{MASK}"/>
    </linearGradient>
  </defs>
  <g transform="translate(40 40) scale(0.625)">
  {body}
  </g>
  <text x="400" y="222" font-family="{FONT}" font-size="150" font-weight="700" letter-spacing="-3" fill="{text}">View<tspan fill="url(#spectrum)">Prism</tspan></text>
  <text x="406" y="306" font-family="{FONT}" font-size="58" font-weight="500" letter-spacing="1" fill="{sub}">Viewport Pass Exporter</text>
</svg>
'''


def render(browser, svg_path, png_path, width, height, scale=1):
    html = pathlib.Path(tempfile.mkdtemp(prefix='viewprism-logo-')) / 'page.html'
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;padding:0;'
                    f'background:transparent;overflow:hidden}}img{{display:block;width:{width}px;height:{height}px}}'
                    f'</style></head><body><img src="{svg_path.as_uri()}"></body></html>', encoding='utf-8')
    cmd = [browser, '--headless', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
           '--default-background-color=00000000', f'--force-device-scale-factor={scale}',
           f'--window-size={width},{height}', f'--screenshot={png_path}', html.as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    print('rendered', png_path.relative_to(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    files = {
        'viewprism-icon.svg': icon_svg(False),
        'viewprism-icon-small.svg': icon_svg(True),
        'viewprism-wordmark-dark.svg': wordmark_svg('dark'),
        'viewprism-wordmark-light.svg': wordmark_svg('light'),
    }
    for name, text in files.items():
        (OUT / name).write_text(text, encoding='utf-8')
        print('wrote', (OUT / name).relative_to(ROOT))
    if not os.path.exists(a.browser):
        print('browser not found; SVGs written, PNGs not rendered')
        return
    for size in (512, 256, 128):
        render(a.browser, OUT / 'viewprism-icon.svg', OUT / f'viewprism-icon-{size}.png', size, size)
    for size in (64, 32):
        render(a.browser, OUT / 'viewprism-icon-small.svg', OUT / f'viewprism-icon-{size}.png', size, size)
    for theme in ('dark', 'light'):
        render(a.browser, OUT / f'viewprism-wordmark-{theme}.svg', OUT / f'viewprism-wordmark-{theme}.png',
               740, 200, scale=2)


if __name__ == '__main__':
    main()
