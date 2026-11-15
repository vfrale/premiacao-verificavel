"""Figura do Capítulo 6: vantagem do operador nos cenários C4a e C4b.

  python -m avaliacao.figuras --saida resultados --destino figuras/cenarios-c4.pdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SERIES = [  # (cenário, rótulo, cor, textura) - cores: três primeiras posições da paleta categórica
    ("C0", "C0: execução honesta", "#2a78d6", None),
    ("C4a", r"C4a: $s_C$ previsível", "#eb6834", None),
    ("C4b", r"C4b: $s_C$ escolhida após o compromisso", "#1baf7a", "////"),
]
PAINEIS = [("sorteio", "(a) Sorteio", "Contemplações do participante controlado por ciclo", 9),
           ("caixa", "(b) Caixa de recompensa", "Itens raros (4% e 1%) por ciclo", 15)]
TINTA, TINTA_2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"


def _fonte() -> None:
    for caminho in ("/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyretermes-regular.otf",
                    "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyretermes-italic.otf"):
        if Path(caminho).exists():
            font_manager.fontManager.addfont(caminho)
    plt.rcParams.update({"font.family": "TeX Gyre Termes", "mathtext.fontset": "stix",
                         "font.size": 9, "hatch.linewidth": 0.6, "hatch.color": "white"})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="resultados")
    p.add_argument("--destino", default="figuras/cenarios-c4.pdf")
    args = p.parse_args(argv)
    dados = json.loads((Path(args.saida) / "cenarios_analise.json").read_text(encoding="utf-8"))["vantagem"]
    _fonte()
    virgula = FuncFormatter(lambda v, _: f"{v:.1f}".replace(".", ","))

    fig, eixos = plt.subplots(1, 2, figsize=(6.3, 2.75), gridspec_kw={"width_ratios": [9, 15]})
    largura = 0.27
    for eixo, (mec, titulo, rotulo_x, n) in zip(eixos, PAINEIS):
        for i, (cen, rotulo, cor, textura) in enumerate(SERIES):
            dist = dados[f"{cen}/{mec}"]["distribuicao"]
            total = sum(dist.values())
            xs = [k + (i - 1) * largura for k in range(n)]
            ys = [dist.get(str(k), 0) / total for k in range(n)]
            eixo.bar(xs, ys, width=largura * 0.88, color=cor, hatch=textura, label=rotulo,
                     linewidth=0, zorder=2)
        eixo.set_title(titulo, loc="left", fontsize=9, color=TINTA)
        eixo.set_xlabel(rotulo_x, color=TINTA_2)
        eixo.set_xticks(range(n))
        eixo.set_ylim(0, 1.0)
        eixo.yaxis.set_major_formatter(virgula)
        eixo.grid(axis="y", color=GRADE, linewidth=0.6, zorder=0)
        for lado in ("top", "right", "left"):
            eixo.spines[lado].set_visible(False)
        eixo.spines["bottom"].set_color(TINTA_2)
        eixo.tick_params(colors=TINTA_2, length=0)
    eixos[0].set_ylabel("Proporção das execuções", color=TINTA_2)
    alcas, rotulos = eixos[0].get_legend_handles_labels()
    fig.legend(alcas, rotulos, loc="upper center", ncol=3, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, 1.02), handlelength=1.2, columnspacing=1.6)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    Path(args.destino).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.destino)
    fig.savefig(Path(args.destino).with_suffix(".png"), dpi=200)
    print("figura gravada em", args.destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
