#!/usr/bin/env python3
"""Gera assets/radar.svg: painel com radar de linguagens, ranking e estatísticas.

Funciona como um "github stats" próprio: consulta a sua conta pela API do GitHub
(linguagens dos repositórios, commits do último ano, pull requests, estrelas)
e desenha o painel em SVG. Só usa a biblioteca padrão do Python.

Uso local:
  python generate_radar.py --demo        dados de exemplo, sem internet
  GH_USER=seu-usuario GITHUB_TOKEN=ghp_xxx python generate_radar.py

No GitHub Actions (workflow incluído), usuário e token são preenchidos sozinhos.
"""
import html
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "SEU-USUARIO"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = Path(os.environ.get("RADAR_OUT", "assets/radar.svg"))

TOP_N = 5                      # quantas linguagens aparecem (de 3 a 7)
IGNORE_LANGS = set()           # ex.: {"Jupyter Notebook", "HTML"}
ACCENT = "#00f5c4"             # verde-ciano dos títulos, números e radar

NEON = {
    "Python": "#4d8dff", "JavaScript": "#e6ff2e", "Java": "#ffa51f",
    "TypeScript": "#a259ff", "HTML": "#ff4d2e", "CSS": "#ff5dc8",
    "SCSS": "#ff7ad9", "C": "#9aa5ff", "C++": "#ff6fb5", "C#": "#5eff7a",
    "PHP": "#8f9bff", "Go": "#3de0ff", "Rust": "#ff8a5c", "Shell": "#7dff9e",
    "Kotlin": "#c77dff", "Swift": "#ff7a4d", "Ruby": "#ff4d6d", "Dart": "#4de1ff",
    "Vue": "#41ff9a", "Dockerfile": "#5cc8ff", "PLpgSQL": "#6fa8ff",
    "Jupyter Notebook": "#ff9e4d", "Lua": "#6b8bff", "R": "#5aa9ff",
}
FALLBACK = ["#ff9de2", "#9dffb0", "#ffd37a", "#8fd3ff", "#d1a3ff", "#ff9d9d", "#b8ff5c"]
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    pullRequests { totalCount }
    contributionsCollection { totalCommitContributions }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 15, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
  }
}
"""

DEMO_DATA = {
    "langs": {"Python": 520_000, "JavaScript": 380_000, "Java": 200_000,
              "TypeScript": 140_000, "HTML": 100_000, "CSS": 40_000, "Shell": 20_000},
    "stats": {"repos": 23, "commits": 842, "prs": 31, "stars": 12},
}


def graphql(variables):
    if not TOKEN:
        sys.exit("Defina GITHUB_TOKEN (no Actions ele já vem pronto; localmente use um token pessoal).")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "radar-perfil"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as err:
        sys.exit(f"GitHub respondeu {err.code}. Confira o token e o nome de usuário ({USER}).")
    if payload.get("errors"):
        sys.exit("Erro na API do GitHub: " + "; ".join(e.get("message", "?") for e in payload["errors"]))
    if not payload["data"]["user"]:
        sys.exit(f"Usuário '{USER}' não encontrado.")
    return payload["data"]["user"]


def collect(pages):
    """Soma linguagens e estrelas a partir das páginas de resposta da API."""
    langs, stars, first = {}, 0, pages[0]
    for page in pages:
        for repo in page["repositories"]["nodes"]:
            stars += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name not in IGNORE_LANGS:
                    langs[name] = langs.get(name, 0) + edge["size"]
    stats = {
        "repos": first["repositories"]["totalCount"],
        "commits": first["contributionsCollection"]["totalCommitContributions"],
        "prs": first["pullRequests"]["totalCount"],
        "stars": stars,
    }
    return {"langs": langs, "stats": stats}


def fetch():
    pages, after = [], None
    while True:
        user = graphql({"login": USER, "after": after})
        pages.append(user)
        info = user["repositories"]["pageInfo"]
        if not info["hasNextPage"]:
            return collect(pages)
        after = info["endCursor"]


def build_rows(langs):
    if not langs:
        sys.exit("Nenhuma linguagem encontrada nos repositórios públicos.")
    total = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:max(3, min(TOP_N, 7))]
    rows = []
    for i, (name, size) in enumerate(top):
        rows.append({"name": name, "share": size / total * 100,
                     "color": NEON.get(name, FALLBACK[i % len(FALLBACK)])})
    others = max(0.0, 100 - sum(r["share"] for r in rows))
    return rows, others


def pct(p):
    return f"{p:.0f}%" if p >= 10 else f"{p:.1f}%"


def short(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def clip(text, size):
    return text if len(text) <= size else text[: size - 1] + "…"


def text(x, y, s, fill="#ffffff", size=12, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" style="font-family:{FONT};'
            f'font-size:{size}px;fill:{fill};font-weight:{weight}">{html.escape(s)}</text>')


CSS = """.rp{transform-origin:172px 185px;animation:gp 1s ease-out backwards;transition:fill-opacity .2s}
.rp:hover{fill-opacity:.45}
.bf{transform-box:fill-box;transform-origin:left center;animation:gb 1s ease-out backwards;transition:transform .2s}
@keyframes gp{from{transform:scale(0)}}
@keyframes gb{from{transform:scaleX(0)}}
.row{transition:opacity .2s}
.row .hit{fill-opacity:0;transition:fill-opacity .2s}
.row:hover .hit{fill-opacity:.07}
.row:hover .bf{transform:scaleY(2.2)}
.rows:hover .row{opacity:.45}
.rows .row:hover{opacity:1}
.tip{opacity:0;pointer-events:none;transition:opacity .15s}
.pt:hover .tip{opacity:1}
.dot{transition:r .15s}
.pt:hover .dot{r:5.5}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}"""


def render(rows, others, stats, demo):
    n = len(rows)
    cx, cy, radius = 172, 185, 80
    top = rows[0]["share"]

    def pt(i, f):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + radius * f * math.cos(a), cy + radius * f * math.sin(a)

    def poly(fracs):
        return " ".join("%.1f,%.1f" % pt(i, f) for i, f in enumerate(fracs))

    scores = [math.sqrt(r["share"] / top) for r in rows]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 412" width="680" height="412" role="img" '
         f'aria-label="Linguagens mais usadas e estatísticas do GitHub">',
         f"<style>{CSS}</style>",
         '<rect width="680" height="412" rx="8" fill="#030305"/>',
         '<defs><clipPath id="cl"><rect x="363" y="56" width="289" height="8" rx="4"/></clipPath></defs>']
    for x, y, w, h in [(10, 10, 325, 300), (345, 10, 325, 300), (10, 322, 660, 80)]:
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#0b0b0f" stroke="#ffffff" stroke-width="1.5"/>')

    # ---- radar
    o.append(text(28, 38, "Radar de linguagens", ACCENT, 14, weight=500))
    for k in range(1, 5):
        o.append(f'<polygon points="{poly([k / 4] * n)}" fill="none" stroke="#ffffff" stroke-opacity="0.2"/>')
    for i in range(n):
        x, y = pt(i, 1)
        o.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#ffffff" stroke-opacity="0.2"/>')
    o.append(f'<polygon class="rp" points="{poly(scores)}" fill="{ACCENT}" fill-opacity="0.25" '
             f'stroke="{ACCENT}" stroke-width="2"/>')
    for i, r in enumerate(rows):
        x, y = pt(i, 1)
        c, s = math.cos(-math.pi / 2 + 2 * math.pi * i / n), math.sin(-math.pi / 2 + 2 * math.pi * i / n)
        anchor = "start" if c > 0.3 else "end" if c < -0.3 else "middle"
        o.append(text(x + c * 10, y + s * 12 + 4, clip(r["name"], 12), "#ffffff", 11, anchor))
    for i, r in enumerate(rows):
        x, y = pt(i, scores[i])
        label = f'{clip(r["name"], 18)} · {pct(r["share"])}'
        w = round(len(label) * 6.4 + 18)
        if i == 0:
            px, py = x + 10, y - 11
        else:
            px, py = x - w / 2, y - 34
        px = min(max(px, 18), 327 - w)
        py = max(py, 48)
        o.append('<g class="pt">')
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="#ffffff" fill-opacity="0"/>')
        o.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{ACCENT}"/>')
        o.append(f'<g class="tip"><rect x="{px:.1f}" y="{py:.1f}" width="{w}" height="22" rx="4" fill="#030305" stroke="{ACCENT}"/>')
        o.append(text(px + w / 2, py + 15, label, "#ffffff", 11, "middle") + "</g></g>")
    o.append(text(28, 296, "Proporção de código por linguagem, escala raiz quadrada", "#ffffff", 11))

    # ---- ranking
    o.append(text(363, 38, "Principais linguagens", ACCENT, 14, weight=500))
    o.append('<g clip-path="url(#cl)">')
    x = 363.0
    for r in rows + [{"share": others, "color": "#ffffff"}]:
        w = 289 * r["share"] / 100
        o.append(f'<rect x="{x:.1f}" y="56" width="{w:.1f}" height="8" fill="{r["color"]}"/>')
        x += w
    o.append('</g><g class="rows">')
    step = 42 if n <= 5 else (285 - 98) / (n - 1)
    for k, r in enumerate(rows):
        y = 98 + k * step
        o.append('<g class="row">')
        o.append(f'<rect class="hit" x="353" y="{y - 18:.1f}" width="309" height="{min(40, step - 2):.1f}" rx="4" fill="#ffffff"/>')
        o.append(f'<circle cx="369" cy="{y - 4:.1f}" r="5" fill="{r["color"]}"/>')
        o.append(text(382, y, clip(r["name"], 24), "#ffffff", 13, weight=500 if k == 0 else 400))
        o.append(text(652, y, pct(r["share"]), ACCENT, 13, "end"))
        o.append(f'<rect x="363" y="{y + 10:.1f}" width="289" height="4" rx="2" fill="#1f1f26"/>')
        o.append(f'<rect class="bf" style="animation-delay:{k * 0.12:.2f}s" x="363" y="{y + 10:.1f}" '
                 f'width="{289 * r["share"] / top:.1f}" height="4" rx="2" fill="{r["color"]}"/>')
        o.append("</g>")
    o.append("</g>")
    stamp = "dados de exemplo" if demo else f"atualizado em {date.today().isoformat()}"
    o.append(text(363, 298, stamp, "#ffffff", 11))

    # ---- estatísticas
    tiles = [("Repositórios", stats["repos"]), ("Commits no último ano", stats["commits"]),
             ("Pull requests", stats["prs"]), ("Estrelas recebidas", stats["stars"])]
    for k, (label, value) in enumerate(tiles):
        x0 = 28 + k * 165
        o.append(text(x0, 350, label, "#ffffff", 11))
        o.append(text(x0, 382, short(value), ACCENT, 22, weight=500))
        if k:
            o.append(f'<line x1="{x0 - 17}" y1="338" x2="{x0 - 17}" y2="386" stroke="#ffffff" stroke-opacity="0.2"/>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    demo = "--demo" in sys.argv
    data = DEMO_DATA if demo else fetch()
    rows, others = build_rows(data["langs"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows, others, data["stats"], demo), encoding="utf-8")
    print(f"ok: {OUT} | {', '.join(r['name'] for r in rows)} | {data['stats']}")


if __name__ == "__main__":
    main()
