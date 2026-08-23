"""Every number the pitch deck and the write-ups quote, derived from the data.

The deck hard-codes standings in prose ("2nd of 17, +403,758"). Those go stale the
moment another Game settles, and a wrong number on a slide is worse than no number.
This script recomputes all of them using ``pitch_figures``' own definitions, so the
prose and the figures can never disagree.

Usage:
    /usr/bin/python3 case_analysis/deck_numbers.py
"""

from __future__ import annotations

from statistics import mean, pstdev

import pitch_figures as pf  # noqa: E402  (same directory)


def eur(x: float) -> str:
    return f"{x:+,.0f}".replace("-", "−")


def rank_of(order: list[tuple[str, float]], team: str) -> int:
    return [t for t, _ in order].index(team) + 1


def main() -> None:
    games, teams, bal = pf.load_balance()
    n = games[-1]
    nets = {t: pf.per_game_nets(bal[t]) for t in teams}

    print(f"SETTLED GAMES: {n}   teams: {len(teams)}\n")

    # ---- season total -----------------------------------------------------
    season = sorted(((t, bal[t][-1]) for t in teams), key=lambda x: -x[1])
    print(f"SEASON TOTAL: {pf.US} is {rank_of(season, pf.US)} of {len(teams)}, "
          f"{eur(dict(season)[pf.US])}")
    for t, v in season[:5]:
        print(f"    {eur(v):>12}  {t}")

    # ---- rebased cuts -----------------------------------------------------
    for label, start in (("ANCHOR", pf.REBASE_ANCHOR),
                         ("SENSITIVITY", pf.REBASE_SENSITIVITY)):
        i0 = games.index(start)
        tot = sorted(((t, sum(nets[t][i0:])) for t in teams), key=lambda x: -x[1])
        r = rank_of(tot, pf.US)
        mine = dict(tot)[pf.US]
        print(f"\nREBASED at Game {start} ({label}) -- {len(games) - i0} Games: "
              f"{pf.US} is {r} of {len(teams)}, {eur(mine)}")
        for t, v in tot[:4]:
            print(f"    {eur(v):>12}  {t}")
        if r > 1:
            ab, av = tot[r - 2]
            print(f"    -> {ab} leads us by {av - mine:,.0f}")
        if r < len(tot):
            bl, bv = tot[r]
            print(f"    -> we lead {bl} by {mine - bv:,.0f}")

    # ---- the era sentence -------------------------------------------------
    era_end = pf.ERAS[0][1]
    print(f"\nERA SENTENCE: deficit is Games 1-{era_end}; "
          f"'over the {n - era_end} Games since'")

    # ---- consistency windows ---------------------------------------------
    for span in (30, 20):
        i0 = len(games) - span
        lo, hi = games[i0], games[-1]
        st = []
        for t in teams:
            v = nets[t][i0:]
            m, s = mean(v), pstdev(v)
            st.append(dict(team=t, mean=m, sd=s, ratio=m / s if s else 0.0,
                           losses=sum(1 for x in v if x < 0), worst=min(v)))
        by_ratio = sorted(st, key=lambda d: -d["ratio"])
        me = next(d for d in st if d["team"] == pf.US)
        r_ratio = by_ratio.index(me) + 1
        r_sd = sorted(st, key=lambda d: d["sd"]).index(me) + 1
        by_loss = sorted(st, key=lambda d: d["losses"])
        r_loss = by_loss.index(me) + 1
        big = [d for d in st if d["worst"] < -80_000]
        fewer = [d for d in st if d["losses"] < me["losses"]]
        print(f"\nLAST {span} GAMES -- G{lo}-G{hi}")
        print(f"    mean/sigma        {me['ratio']:.2f}   rank {r_ratio} of {len(st)}")
        print(f"    losing Games      {me['losses']} / {span}   rank {r_loss}")
        print(f"    worst single Game {me['worst']:,.0f}")
        print(f"    sigma rank        {r_sd} of {len(st)}")
        print(f"    teams with a Game worse than -80,000: {len(big)}")
        for d in fewer:
            print(f"    fewer losing Games: {d['team']} ({d['losses']}), "
                  f"worst {d['worst']:,.0f}")
        if span == 30:
            print("    top of field by mean/sigma: " +
                  ", ".join(f"{d['team']} {d['ratio']:.2f}" for d in by_ratio[:3]))


if __name__ == "__main__":
    main()
