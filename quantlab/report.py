"""Génération du rapport HTML — lisible sans savoir coder.

SVG inline, aucune dépendance externe, aucun CDN : le fichier s'ouvre dans
n'importe quel navigateur, hors ligne. Thème clair/sombre suivant le réglage
du système.
"""
from __future__ import annotations

import html
import math

import numpy as np
import pandas as pd

# Palette catégorielle validée (clair + sombre), 3 emplacements.
PAL = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70")]


def _esc(s) -> str:
    return html.escape(str(s))


def _nice_ticks(lo: float, hi: float, n: int = 5):
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return [lo, hi]
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min([1, 2, 2.5, 5, 10], key=lambda m: abs(m * mag - raw)) * mag
    start = math.floor(lo / step) * step
    out, v = [], start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.5:
            out.append(v)
        v += step
    return out


def line_chart(series: dict, title: str, y_fmt="{:.2f}", height=300, y_label=""):
    """Courbe(s) dans le temps. series = {nom: (x_dates, y_values)}."""
    W, H = 860, height
    ml, mr, mt, mb = 62, 120, 16, 34
    pw, ph = W - ml - mr, H - mt - mb

    all_y = np.concatenate([np.asarray(v, float) for _, v in series.values()])
    all_y = all_y[np.isfinite(all_y)]
    if all_y.size == 0:
        return "<p>pas de données</p>"
    lo, hi = float(all_y.min()), float(all_y.max())
    if hi <= lo:
        hi = lo + 1.0
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad

    n = max(len(v[1]) for v in series.values())
    sx = lambda i: ml + (i / max(n - 1, 1)) * pw
    sy = lambda y: mt + ph - (y - lo) / (hi - lo) * ph

    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="{_esc(title)}" class="chart">']

    # Grille et axe Y — récessifs.
    for t in _nice_ticks(lo, hi):
        y = sy(t)
        parts.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{ml-10}" y="{y+4:.1f}" class="tick" text-anchor="end">'
                     f'{_esc(y_fmt.format(t))}</text>')

    # Axe X : quelques dates seulement.
    first = list(series.values())[0][0]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        i = int(frac * (n - 1))
        if i < len(first):
            lbl = _esc(pd.Timestamp(first[i]).strftime("%b %y"))
            # Le premier et le dernier label sont ancrés vers l'intérieur, sinon
            # ils débordent sous les graduations de l'axe Y / hors du cadre.
            anchor = "start" if frac == 0.0 else ("end" if frac == 1.0 else "middle")
            parts.append(f'<text x="{sx(i):.1f}" y="{H-12}" class="tick" '
                         f'text-anchor="{anchor}">{lbl}</text>')

    for k, (name, (xs, ys)) in enumerate(series.items()):
        c_l, c_d = PAL[k % len(PAL)]
        ys = np.asarray(ys, float)
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(ys) if np.isfinite(v))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{c_l}" '
                     f'stroke-width="2" stroke-linejoin="round" class="s{k}"/>')
        # Étiquette directe : l'identité ne repose jamais sur la seule couleur.
        if np.isfinite(ys[-1]):
            parts.append(f'<text x="{ml+pw+10}" y="{sy(ys[-1])+4:.1f}" '
                         f'class="dlabel dl{k}">{_esc(name)}</text>')

    parts.append('</svg>')
    return "".join(parts)


def histogram(values, observed: float, title: str, x_fmt="{:.2f}",
              height=260, label_obs="observé"):
    """Distribution d'une simulation, avec repère sur la valeur observée."""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return "<p>pas de données</p>"

    W, H = 860, height
    ml, mr, mt, mb = 62, 24, 26, 40
    pw, ph = W - ml - mr, H - mt - mb

    lo, hi = float(v.min()), float(v.max())
    if np.isfinite(observed):
        lo, hi = min(lo, observed), max(hi, observed)
    if hi <= lo:
        hi = lo + 1.0
    pad = (hi - lo) * 0.05
    lo, hi = lo - pad, hi + pad

    nb = 34
    counts, edges = np.histogram(v, bins=nb, range=(lo, hi))
    cmax = max(1, counts.max())
    sx = lambda x: ml + (x - lo) / (hi - lo) * pw

    c_l = PAL[0][0]
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="{_esc(title)}" class="chart">']

    for i, c in enumerate(counts):
        if c == 0:
            continue
        x0, x1 = sx(edges[i]), sx(edges[i + 1])
        bh = c / cmax * ph
        # 2px de respiration entre barres adjacentes.
        parts.append(f'<rect x="{x0+1:.1f}" y="{mt+ph-bh:.1f}" '
                     f'width="{max(1.0,x1-x0-2):.1f}" height="{bh:.1f}" '
                     f'rx="2" fill="{c_l}" opacity="0.55" class="bar"/>')

    if np.isfinite(observed):
        x = sx(observed)
        parts.append(f'<line x1="{x:.1f}" y1="{mt-6}" x2="{x:.1f}" y2="{mt+ph}" '
                     f'stroke="{PAL[1][0]}" stroke-width="2" class="obs"/>')
        anchor = "end" if x > ml + pw * 0.7 else "start"
        dx = -8 if anchor == "end" else 8
        parts.append(f'<text x="{x+dx:.1f}" y="{mt-10}" class="dlabel dl1" '
                     f'text-anchor="{anchor}">{_esc(label_obs)} '
                     f'{_esc(x_fmt.format(observed))}</text>')

    for t in _nice_ticks(lo, hi, 6):
        parts.append(f'<text x="{sx(t):.1f}" y="{H-14}" class="tick" '
                     f'text-anchor="middle">{_esc(x_fmt.format(t))}</text>')
    parts.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" class="axis"/>')
    parts.append('</svg>')
    return "".join(parts)


def stat_tile(label: str, value: str, verdict: str = "", hint: str = "") -> str:
    cls = {"ok": "v-ok", "bad": "v-bad", "warn": "v-warn"}.get(verdict, "")
    return (f'<div class="tile"><div class="tile-l">{_esc(label)}</div>'
            f'<div class="tile-v {cls}">{_esc(value)}</div>'
            f'{f"<div class=tile-h>{_esc(hint)}</div>" if hint else ""}</div>')


def table(rows: list[dict], cols: list[str], headers: list[str] | None = None) -> str:
    headers = headers or cols
    h = "".join(f"<th>{_esc(x)}</th>" for x in headers)
    body = []
    for r in rows:
        tds = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, float):
                v = f"{v:,.3f}"
            tds.append(f"<td>{_esc(v)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div class="tw"><table><thead><tr>{h}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--surface:#ffffff;--border:#e6e5e0;
--text:#0b0b0b;--text2:#52514e;--muted:#8a8880;--grid:#eceae4;
--s0:#2a78d6;--s1:#eb6834;--s2:#1baf7a;--ok:#008300;--bad:#e34948;--warn:#eda100;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#141413;--surface:#1a1a19;--border:#302f2c;--text:#ffffff;--text2:#c3c2b7;
--muted:#8a8880;--grid:#2a2926;--s0:#3987e5;--s1:#d95926;--s2:#199e70;
--ok:#4ba84b;--bad:#e66767;--warn:#c98500;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
.wrap{max-width:940px;margin:0 auto;padding-block:32px;padding-left:20px;padding-right:20px;}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:19px;margin:38px 0 6px;letter-spacing:-.01em}
h3{font-size:15px;margin:22px 0 6px;color:var(--text2)}
p{color:var(--text2);margin:8px 0}
.sub{color:var(--muted);font-size:13px;margin-bottom:24px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:18px;margin:14px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px}
.tile-l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.tile-v{font-size:26px;font-weight:600;margin-top:4px;letter-spacing:-.02em}
.tile-h{font-size:12px;color:var(--muted);margin-top:3px}
.v-ok{color:var(--ok)}.v-bad{color:var(--bad)}.v-warn{color:var(--warn)}
.chart{display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--border);stroke-width:1}
.tick{fill:var(--muted);font-size:11px}
.dlabel{font-size:12px;font-weight:600}
.dl0{fill:var(--s0)}.dl1{fill:var(--s1)}.dl2{fill:var(--s2)}
.s0{stroke:var(--s0)}.s1{stroke:var(--s1)}.s2{stroke:var(--s2)}
.bar{fill:var(--s0)}.obs{stroke:var(--s1)}
.tw{overflow-x:auto;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:420px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);
white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.04em}
.note{border-left:3px solid var(--warn);padding:10px 14px;background:var(--surface);
border-radius:0 8px 8px 0;margin:14px 0;font-size:14px;color:var(--text2)}
.bad-note{border-left-color:var(--bad)}
.ok-note{border-left-color:var(--ok)}
code{background:var(--grid);padding:1px 5px;border-radius:4px;font-size:13px}
"""


def build_page(title: str, subtitle: str, blocks: list[str]) -> str:
    return (f"<title>{_esc(title)}</title><style>{CSS}</style>"
            f'<div class="wrap"><h1>{_esc(title)}</h1>'
            f'<div class="sub">{_esc(subtitle)}</div>'
            + "".join(blocks) + "</div>")
