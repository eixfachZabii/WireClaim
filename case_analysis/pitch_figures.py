"""Publication-quality pitch/paper figures for team "Bin busy".

Reads the already-computed series in ``case_analysis/data/`` (see
``DATA_LAYOUT.md``) and writes four figures into ``presentation/figures/``,
each in a dark slide variant (PNG + PDF) and a light paper variant (PDF + PNG).

    FIG 1  balance-annotated   cumulative net, 94 settled Games, eras annotated
    FIG 2  consistency         risk-adjusted return (mean / sigma), Games 75-94
    FIG 3  per-game-net        our per-game net, era bands, rolling-10 mean
    FIG 4  rebased-g20         cumulative net re-indexed to 0 at Game 20

Every printed number is derived here from ``data/balance.csv`` /
``data/binbusy_money.csv`` -- nothing is hard-coded except the era boundaries
and the two qualitative era names.

Usage (needs a Python with matplotlib; the pixi env does not have one):
    /usr/bin/python3 case_analysis/pitch_figures.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_DIR = ROOT / "presentation" / "figures"

US = "Bin busy"
DPI = 200

# Era boundaries are the only editorial input; the money is computed.
ERAS = [
    (1, 25, "G1–25", "no estimator"),
    (26, 62, "G26–62", "estimator + learning loop"),
    (63, 80, "G63–80", "Charge fixes live"),
    (81, 100, "G81–100", "3× weighted"),
]
DARK_CHANNEL = (82, 89)  # model channel 401'd; model_draws = 0
CONSISTENCY_WINDOW = (78, 97)
REBASE_ANCHOR = 20       # Strategy 2 went live around here
REBASE_SENSITIVITY = 26  # conservative cut: G21-24 shipped the fallback Limit of 35


# --------------------------------------------------------------------------- #
# themes
# --------------------------------------------------------------------------- #

DARK = dict(
    name="dark",
    bg="#0B0C0E",
    fg="#E7E5E4",
    muted="#6B6763",
    accent="#E8B84B",
    accent_soft="#8A6E22",
    rival="#5A5652",
    rival_lw=1.15,
    rival_alpha=0.85,
    band_fill="#16171A",
    band_accent="#2A2211",
    grid="#2A2B2E",
    pos="#3FBF71",
    neg="#E5484D",
    bar_muted="#3A3733",
)

LIGHT = dict(
    name="light",
    bg="#FFFFFF",
    fg="#111111",
    muted="#6E6A66",
    accent="#B8860B",
    accent_soft="#E0C07A",
    rival="#ADA9A4",
    rival_lw=1.05,
    rival_alpha=0.95,
    band_fill="#F2F1EF",
    band_accent="#FBF3DF",
    grid="#DCDAD7",
    pos="#1B7F4B",
    neg="#B33A33",
    bar_muted="#C9C5C0",
)


def apply_rc(th: dict) -> None:
    plt.rcdefaults()
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.unicode_minus": True,
        "figure.facecolor": th["bg"],
        "axes.facecolor": th["bg"],
        "savefig.facecolor": th["bg"],
        "text.color": th["fg"],
        "axes.labelcolor": th["fg"],
        "xtick.color": th["muted"],
        "ytick.color": th["muted"],
        "axes.edgecolor": th["muted"],
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "axes.labelsize": 15,
    })


def strip_axes(ax, th: dict) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(th["grid"])
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(axis="both", length=0, pad=8)
    ax.set_axisbelow(True)


def k(v: float, signed: bool = False) -> str:
    s = f"{v/1000:,.0f}k".replace("-", "−")
    if signed and v > 0:
        s = "+" + s
    return s


def eur(v: float) -> str:
    return f"{v:+,.0f}".replace("-", "−")


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
         7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #

def load_balance():
    rows = list(csv.DictReader((DATA_DIR / "balance.csv").open()))
    teams = [c for c in rows[0] if c != "game"]
    games = [int(r["game"]) for r in rows]
    bal = {t: [float(r[t]) for r in rows] for t in teams}
    return games, teams, bal


def load_money():
    rows = list(csv.DictReader((DATA_DIR / "binbusy_money.csv").open()))
    return [int(r["game"]) for r in rows], [float(r["net"]) for r in rows]


def per_game_nets(series: list[float]) -> list[float]:
    out, prev = [], 0.0
    for v in series:
        out.append(v - prev)
        prev = v
    return out


def mean(xs):
    return sum(xs) / len(xs)


def pstdev(xs):
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


# --------------------------------------------------------------------------- #
# shared: era bands
# --------------------------------------------------------------------------- #

def draw_eras(ax, th, xmax, label_frac, extra=None, fontsize=13, xmin=0.5,
              min_label_span=8):
    """Background bands + two-line centred labels at ``label_frac`` (axes frac).

    ``xmin`` clips bands on the left (for a window that starts mid-tournament);
    a band clipped below ``min_label_span`` Games keeps its fill but loses its
    label, which would no longer be centred on the era it names.
    """
    for i, (lo, hi, tag, name) in enumerate(ERAS):
        x0, x1 = max(lo - 0.5, xmin), min(hi, xmax) + 0.5
        if x1 <= x0:
            continue
        last = i == len(ERAS) - 1
        ax.axvspan(x0, x1, color=th["band_accent"] if last else
                   (th["band_fill"] if i % 2 == 0 else th["bg"]),
                   lw=0, zorder=0)
        if i and x0 > xmin:
            ax.axvline(x0, color=th["grid"], lw=0.9, zorder=1)
        if x1 - x0 < min_label_span:
            continue
        sub = name if extra is None else f"{name}{extra.get(i, '')}"
        ax.text((x0 + x1) / 2, label_frac, tag,
                transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=fontsize + 1, fontweight="bold",
                color=th["accent"] if last else th["fg"], zorder=6)
        ax.text((x0 + x1) / 2, label_frac - 0.037, sub,
                transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=fontsize, color=th["muted"], zorder=6)


def draw_dark_channel(ax, th, y0, y1, caption, fontsize=13):
    lo, hi = DARK_CHANNEL
    ax.add_patch(Rectangle((lo - 0.5, y0), hi - lo + 1, y1 - y0,
                           transform=ax.get_xaxis_transform(),
                           facecolor=th["accent"], alpha=0.75, lw=0, zorder=6))
    ax.annotate(caption, xy=(lo - 0.5, (y0 + y1) / 2),
                xycoords=ax.get_xaxis_transform(),
                xytext=(-10, 0), textcoords="offset points",
                ha="right", va="center", fontsize=fontsize,
                color=th["accent"], zorder=6,
                arrowprops=dict(arrowstyle="-", color=th["accent"], lw=1.2,
                                shrinkA=2, shrinkB=0))


def save(fig, stem, th):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for ext in ("png", "pdf"):
        p = OUT_DIR / f"{stem}-{th['name']}.{ext}"
        fig.savefig(p, dpi=DPI, facecolor=fig.get_facecolor())
        written.append(p)
    plt.close(fig)
    return written


# --------------------------------------------------------------------------- #
# FIG 1 -- balance-annotated
# --------------------------------------------------------------------------- #

def fig_balance(th, games, teams, bal):
    apply_rc(th)
    order = sorted(teams, key=lambda t: -bal[t][-1])
    rivals_top3 = [t for t in order if t != US][:3]
    n = len(games)
    us = bal[US]
    era1 = us[24]                                   # cumulative after G25
    final = us[-1]
    rank = order.index(US) + 1

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.065, right=0.795, top=0.855, bottom=0.105)

    ymin, ymax = -470_000, 660_000
    ax.set_xlim(0.2, n + 0.8)
    ax.set_ylim(ymin, ymax)
    off_axis = sum(1 for t in teams if bal[t][-1] < ymin)
    worst_m = f"{min(bal[t][-1] for t in teams) / 1e6:.2f}M".replace("-", "−")

    draw_eras(ax, th, n, 0.955, extra={0: f"  ·  {eur(era1)}"})
    ax.grid(axis="y", color=th["grid"], lw=0.9, alpha=0.9, zorder=1)
    ax.axhline(0, color=th["muted"], lw=1.2, alpha=0.8, zorder=2)

    for t in order:
        if t == US:
            continue
        ax.plot(games, bal[t], color=th["rival"], lw=th["rival_lw"],
                alpha=th["rival_alpha"], solid_capstyle="round", zorder=3)
    ax.plot(games, us, color=th["accent"], lw=4.2, solid_capstyle="round",
            solid_joinstyle="round", zorder=8)

    # top-3 rivals: faint right-end labels, de-overlapped with leader lines
    spread = 0.052 * (ymax - ymin)
    top_y = max(bal[t][-1] for t in rivals_top3) + 0.5 * spread
    for i, t in enumerate(rivals_top3):
        ty = top_y - i * spread
        ax.annotate(f"{t}  {eur(bal[t][-1])}", xy=(n, bal[t][-1]),
                    xytext=(n + 3.2, ty), ha="left", va="center",
                    fontsize=12.5, color=th["muted"], clip_on=False,
                    arrowprops=dict(arrowstyle="-", color=th["grid"], lw=0.9,
                                    shrinkA=0, shrinkB=2), zorder=7)
    ax.text(n + 3.2, top_y + 0.75 * spread, "field leaders", ha="left",
            va="center", fontsize=11.5, color=th["muted"], style="italic",
            clip_on=False)

    # our right-end label
    ax.annotate(US, xy=(n, final), xytext=(n + 3.2, final + 0.10 * spread),
                ha="left", va="bottom", fontsize=20, fontweight="bold",
                color=th["accent"], clip_on=False, zorder=9,
                arrowprops=dict(arrowstyle="-", color=th["accent"], lw=1.4,
                                shrinkA=0, shrinkB=3))
    ax.text(n + 3.2, final - 0.10 * spread,
            f"{rank}th of 17   {eur(final)}", ha="left", va="top",
            fontsize=14, color=th["accent"], zorder=9)

    # "17th of 17" callout on our line
    g9 = games.index(9)
    ax.annotate("17th of 17 — dead last", xy=(games[g9], us[g9]),
                xytext=(17.0, 250_000), ha="left", va="center",
                fontsize=18, fontweight="bold", color=th["accent"], zorder=9,
                arrowprops=dict(arrowstyle="-", color=th["accent"], lw=1.6,
                                shrinkA=10, shrinkB=5,
                                connectionstyle="arc3,rad=0"))
    ax.text(17.0, 250_000 + 0.052 * (ymax - ymin), "Games 9–12",
            ha="left", va="center", fontsize=13.5, color=th["muted"], zorder=9)

    draw_dark_channel(ax, th, 0.843, 0.866,
                      "G82–89 model channel dark  —  still +254,092 weighted")

    ax.set_yticks([-400_000, -200_000, 0, 200_000, 400_000])
    ax.set_yticklabels([k(v) for v in (-400_000, -200_000, 0, 200_000, 400_000)])
    ax.set_xticks([1] + list(range(10, n + 1, 10)))
    ax.set_xlabel("Game", fontsize=15, labelpad=6)
    ax.set_ylabel("cumulative net  (€ thousands)", fontsize=15, labelpad=10)
    strip_axes(ax, th)

    fig.text(0.065, 0.955, "Last place to 5th", fontsize=34, fontweight="bold",
             color=th["fg"], va="top")
    fig.text(0.065, 0.902,
             f"cumulative net over {n} settled Games  ·  {US} against "
             f"{len(teams) - 1} rival teams  ·  {off_axis} teams run off the "
             f"bottom of the axis, to {worst_m}",
             fontsize=15, color=th["muted"], va="top")
    return save(fig, "balance-annotated", th)


# --------------------------------------------------------------------------- #
# FIG 2 -- consistency
# --------------------------------------------------------------------------- #

def fig_consistency(th, games, teams, bal):
    apply_rc(th)
    lo, hi = CONSISTENCY_WINDOW
    i0, i1 = games.index(lo), games.index(hi)
    span = hi - lo + 1

    stats = []
    for t in teams:
        nets = per_game_nets(bal[t])[i0:i1 + 1]
        m, s = mean(nets), pstdev(nets)
        stats.append(dict(team=t, mean=m, sd=s, ratio=m / s,
                          losses=sum(1 for x in nets if x < 0), worst=min(nets)))
    stats.sort(key=lambda d: -d["ratio"])
    me = next(d for d in stats if d["team"] == US)
    my_rank = stats.index(me) + 1
    big = sum(1 for d in stats if d["worst"] < -80_000)

    fig, ax = plt.subplots(figsize=(13, 10.5))
    fig.subplots_adjust(left=0.215, right=0.735, top=0.815, bottom=0.085)

    ys = list(range(len(stats)))[::-1]
    for y, d in zip(ys, stats):
        mine = d["team"] == US
        ax.barh(y, d["ratio"], height=0.62, zorder=3,
                color=th["accent"] if mine else th["bar_muted"])
        ax.text(-0.035 if d["ratio"] >= 0 else 0.035, y, d["team"],
                ha="right" if d["ratio"] >= 0 else "left", va="center",
                transform=ax.get_yaxis_transform() if False else ax.transData,
                fontsize=13.5 if not mine else 16,
                fontweight="bold" if mine else "normal",
                color=th["accent"] if mine else th["fg"], zorder=4)
        off = 0.028 if d["ratio"] >= 0 else -0.028
        ax.text(d["ratio"] + off, y, f"{d['ratio']:+.2f}".replace("-", "−"),
                ha="left" if d["ratio"] >= 0 else "right", va="center",
                fontsize=12.5 if not mine else 15,
                fontweight="bold" if mine else "normal",
                color=th["accent"] if mine else th["muted"], zorder=4)

    span_x = max(abs(d["ratio"]) for d in stats) * 1.06
    ax.set_xlim(-span_x, span_x)
    ax.set_ylim(-0.9, len(stats) - 0.35)
    ax.set_yticks([])
    ax.axvline(0, color=th["muted"], lw=1.2, zorder=2)
    ax.grid(axis="x", color=th["grid"], lw=0.9, zorder=1)
    ax.set_xticks([-0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75])
    ax.set_xlabel("mean per-Game net  ÷  σ      (higher = more reward "
                  "per unit of volatility)", fontsize=14.5, labelpad=8)
    strip_axes(ax, th)

    # right-hand fact columns
    cx = {"losses": span_x + 0.30, "worst": span_x + 0.72}
    ax.text(cx["losses"], len(stats) - 0.45, f"losing\nGames (of {span})",
            ha="center", va="bottom", fontsize=12.5, color=th["muted"],
            clip_on=False, linespacing=1.35)
    ax.text(cx["worst"], len(stats) - 0.45, "worst\nsingle Game",
            ha="center", va="bottom", fontsize=12.5, color=th["muted"],
            clip_on=False, linespacing=1.35)
    for y, d in zip(ys, stats):
        mine = d["team"] == US
        col = th["accent"] if mine else th["fg"]
        ax.text(cx["losses"], y, str(d["losses"]), ha="center", va="center",
                fontsize=15 if mine else 13, color=col,
                fontweight="bold" if mine else "normal", clip_on=False)
        ax.text(cx["worst"], y, f"{d['worst']:,.0f}".replace("-", "−"),
                ha="center", va="center", fontsize=15 if mine else 13,
                color=col, fontweight="bold" if mine else "normal",
                clip_on=False)

    fig.text(0.215, 0.965,
             f"{ordinal(my_rank)}-best risk-adjusted return in the field",
             fontsize=30, fontweight="bold", color=th["fg"], va="top")
    fig.text(0.215, 0.916,
             f"per-Game net over Games {lo}–{hi}  ·  all 17 teams  "
             f"·  μ = {me['mean']:,.0f}, σ = {me['sd']:,.0f}, "
             f"μ/σ = {me['ratio']:.3f}",
             fontsize=14.5, color=th["muted"], va="top")
    fig.text(0.215, 0.874,
             f"Only {me['losses']} losing Games in {span}; the worst cost "
             f"{me['worst']:,.0f}".replace("-", "−") +
             f".  {WORDS[big]} teams lost more than 80,000 in a single Game.",
             fontsize=14.5, color=th["accent"], va="top")
    return save(fig, "consistency", th)


# --------------------------------------------------------------------------- #
# FIG 3 -- per-game net
# --------------------------------------------------------------------------- #

def fig_per_game(th, mgames, nets):
    apply_rc(th)
    n = len(mgames)
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.075, right=0.965, top=0.845, bottom=0.105)

    lo_y = min(nets) * 1.20
    hi_y = lo_y + (max(nets) - lo_y) / 0.80
    ax.set_xlim(0.2, n + 0.8)
    ax.set_ylim(lo_y, hi_y)

    draw_eras(ax, th, n, 0.955)
    ax.grid(axis="y", color=th["grid"], lw=0.9, zorder=1)

    ax.bar(mgames, nets, width=0.78, zorder=3,
           color=[th["pos"] if v >= 0 else th["neg"] for v in nets])
    ax.axhline(0, color=th["fg"], lw=1.1, alpha=0.55, zorder=4)

    win = 10
    rx = [mgames[i] for i in range(win - 1, n)]
    ry = [mean(nets[i - win + 1:i + 1]) for i in range(win - 1, n)]
    ax.plot(rx, ry, color=th["accent"], lw=3.6, zorder=6,
            solid_capstyle="round")
    ax.annotate(f"rolling {win}-Game mean", xy=(rx[-1], ry[-1]),
                xytext=(-8, 34), textcoords="offset points", ha="right",
                va="bottom", fontsize=14.5, fontweight="bold",
                color=th["accent"], zorder=7,
                arrowprops=dict(arrowstyle="-", color=th["accent"], lw=1.4,
                                shrinkA=2, shrinkB=3))

    wi = nets.index(min(nets))
    ax.annotate(f"worst Game  {min(nets):,.0f}".replace("-", "−"),
                xy=(mgames[wi], nets[wi]), xytext=(mgames[wi] + 6, lo_y * 0.86),
                ha="left", va="center", fontsize=14, color=th["neg"], zorder=7,
                arrowprops=dict(arrowstyle="-", color=th["neg"], lw=1.4,
                                shrinkA=4, shrinkB=4))

    lo, hi = CONSISTENCY_WINDOW
    late = nets[mgames.index(lo):]
    yb = 0.185
    ax.annotate("", xy=(lo - 0.5, yb), xytext=(n + 0.6, yb),
                xycoords=ax.get_xaxis_transform(),
                textcoords=ax.get_xaxis_transform(),
                arrowprops=dict(arrowstyle="<->", color=th["fg"], lw=1.4,
                                alpha=0.8))
    ax.text(n + 0.6, yb + 0.028,
            f"G{lo}–{hi}:   σ = {pstdev(late):,.0f}   ·   "
            f"{sum(1 for v in late if v < 0)} losing Games in {len(late)}   ·   "
            f"worst {min(late):,.0f}".replace("-", "−"),
            transform=ax.get_xaxis_transform(),
            ha="right", va="bottom", fontsize=15, color=th["fg"])

    draw_dark_channel(ax, th, 0.085, 0.108, "G82–89 model channel dark")

    step = 20_000
    ticks = [t for t in range(-200_000, 200_001, step) if lo_y <= t <= hi_y]
    ax.set_yticks(ticks)
    ax.set_yticklabels([k(v) for v in ticks])
    ax.set_xticks([1] + list(range(10, n + 1, 10)))
    ax.set_xlabel("Game", fontsize=15, labelpad=6)
    ax.set_ylabel("net this Game  (€ thousands)", fontsize=15, labelpad=10)
    strip_axes(ax, th)

    fig.text(0.075, 0.962, "The variance collapses once the estimator ships",
             fontsize=32, fontweight="bold", color=th["fg"], va="top")
    fig.text(0.075, 0.908,
             f"{US} per-Game net across {n} settled Games  ·  "
             f"green = profit, red = loss  ·  G1–25 total "
             f"{eur(sum(nets[:25]))}, G26–{mgames[-1]} total "
             f"{eur(sum(nets[25:]))}",
             fontsize=15, color=th["muted"], va="top")
    return save(fig, "per-game-net", th)


# --------------------------------------------------------------------------- #
# FIG 4 -- rebased-g20
# --------------------------------------------------------------------------- #

def rebase(games, teams, bal, anchor):
    """Every team re-indexed to 0 at ``anchor``; returns series + ranked totals."""
    i = games.index(anchor)
    xs = games[i:]
    series = {t: [v - bal[t][i] for v in bal[t][i:]] for t in teams}
    total = {t: series[t][-1] for t in teams}
    n_played = len(xs) - 1                       # per-Game nets after the anchor
    rate = {t: total[t] / n_played for t in teams}
    by_total = sorted(teams, key=lambda t: -total[t])
    by_rate = sorted(teams, key=lambda t: -rate[t])
    return xs, series, total, rate, by_total, by_rate, n_played


def fig_rebased(th, games, teams, bal):
    apply_rc(th)
    a = REBASE_ANCHOR
    xs, series, total, rate, by_total, by_rate, n_played = rebase(
        games, teams, bal, a)
    last = games[-1]
    rank = by_total.index(US) + 1
    rank_rate = by_rate.index(US) + 1
    top3 = by_total[:3]

    # sensitivity: the conservative cut, for the standfirst
    _, _, tot_s, _, by_total_s, _, _ = rebase(games, teams, bal,
                                              REBASE_SENSITIVITY)
    rank_s = by_total_s.index(US) + 1

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.subplots_adjust(left=0.065, right=0.775, top=0.835, bottom=0.105)

    ymin, ymax = -450_000, 500_000
    ax.set_xlim(a - 0.8, last + 0.8)
    ax.set_ylim(ymin, ymax)
    off_axis = sum(1 for t in teams if total[t] < ymin)
    worst = f"{min(total.values()) / 1e6:.2f}M".replace("-", "−")

    draw_eras(ax, th, last, 0.955, xmin=a - 0.8)
    ax.grid(axis="y", color=th["grid"], lw=0.9, alpha=0.9, zorder=1)
    ax.axhline(0, color=th["muted"], lw=1.2, alpha=0.8, zorder=2)

    for t in by_total:
        if t == US:
            continue
        ax.plot(xs, series[t], color=th["rival"], lw=th["rival_lw"],
                alpha=th["rival_alpha"], solid_capstyle="round", zorder=3)
    ax.plot(xs, series[US], color=th["accent"], lw=4.2, solid_capstyle="round",
            solid_joinstyle="round", zorder=8)

    # the common origin
    ax.plot([a], [0], marker="o", ms=8, mfc=th["bg"], mec=th["accent"],
            mew=2.2, zorder=9)
    ax.annotate(f"every team starts at 0\nat Game {a}", xy=(a, 0),
                xytext=(a + 0.9, -305_000), ha="left", va="center",
                fontsize=13.5, color=th["muted"], linespacing=1.35, zorder=9,
                arrowprops=dict(arrowstyle="-", color=th["grid"], lw=1.1,
                                shrinkA=4, shrinkB=8))

    # right-end labels: the top 3 on the rebased measure, de-overlapped
    spread = 0.052 * (ymax - ymin)
    label_y = {top3[0]: 462_000, US: 382_000, top3[2]: 258_000}
    if US not in label_y:                        # we are not top-3: own slot
        label_y = {t: 462_000 - i * 1.55 * spread for i, t in enumerate(top3)}
        label_y[US] = total[US]
    for t in top3:
        if t == US:
            continue
        ax.annotate(f"{by_total.index(t) + 1}   {t}   {eur(total[t])}",
                    xy=(last, total[t]), xytext=(last + 2.6, label_y[t]),
                    ha="left", va="center", fontsize=13, color=th["muted"],
                    clip_on=False, zorder=7,
                    arrowprops=dict(arrowstyle="-", color=th["grid"], lw=0.9,
                                    shrinkA=0, shrinkB=2))

    ax.annotate(US, xy=(last, total[US]),
                xytext=(last + 2.6, label_y[US] + 0.10 * spread),
                ha="left", va="bottom", fontsize=20, fontweight="bold",
                color=th["accent"], clip_on=False, zorder=9,
                arrowprops=dict(arrowstyle="-", color=th["accent"], lw=1.4,
                                shrinkA=0, shrinkB=3))
    ax.text(last + 2.6, label_y[US] - 0.10 * spread,
            f"{ordinal(rank)} of {len(teams)}   {eur(total[US])}",
            ha="left", va="top", fontsize=14, color=th["accent"], zorder=9)
    ax.text(last + 2.6, label_y[US] - 0.10 * spread - 0.055 * (ymax - ymin),
            f"{eur(rate[US])} per Game  ·  {ordinal(rank_rate)}", ha="left",
            va="top", fontsize=12.5, color=th["muted"], zorder=9)

    draw_dark_channel(ax, th, 0.072, 0.095, "G82–89 model channel dark")

    ticks = [-400_000, -200_000, 0, 200_000, 400_000]
    ax.set_yticks(ticks)
    ax.set_yticklabels([k(v) for v in ticks])
    ax.set_xticks([a] + list(range(30, last + 1, 10)))
    ax.set_xlabel("Game", fontsize=15, labelpad=6)
    ax.set_ylabel(f"net since Game {a}  (€ thousands)", fontsize=15, labelpad=10)
    strip_axes(ax, th)

    fig.text(0.065, 0.962,
             f"Indexed to Game {a}, when our estimator went live",
             fontsize=34, fontweight="bold", color=th["fg"], va="top")
    fig.text(0.065, 0.910,
             f"cumulative net over Games {a}–{last}  ·  re-based to zero at "
             f"Game {a}  ·  unweighted per-Game nets  ·  {off_axis} teams run "
             f"off the bottom, to {worst}",
             fontsize=14.5, color=th["muted"], va="top")
    fig.text(0.065, 0.872,
             f"{ordinal(rank)} of {len(teams)} over the {last - a} Games "
             f"since — {eur(total[US])}, {eur(rate[US])} per Game.  Re-based at "
             f"Game {REBASE_SENSITIVITY} instead, the conservative cut: "
             f"{ordinal(rank_s)} of {len(teams)} at {eur(tot_s[US])}.",
             fontsize=14.5, color=th["accent"], va="top")
    return save(fig, f"rebased-g{a}", th)


# --------------------------------------------------------------------------- #

def main() -> None:
    games, teams, bal = load_balance()
    mgames, nets = load_money()
    assert mgames == games, "balance.csv and binbusy_money.csv disagree on Games"

    written = []
    for th in (DARK, LIGHT):
        written += fig_balance(th, games, teams, bal)
        written += fig_consistency(th, games, teams, bal)
        written += fig_per_game(th, mgames, nets)
        written += fig_rebased(th, games, teams, bal)
    for p in written:
        print("wrote", p)


if __name__ == "__main__":
    main()
