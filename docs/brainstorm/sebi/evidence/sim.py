"""A tournament simulator, so policy choices are settled with numbers.

Models one Game as: draw a Fair Value per Line Item, let every team form a noisy
Estimate of it, let each team's policy turn that Estimate into a Charge and a
Limit, then settle all ordered pairs under the payoff matrix in README section 2.

The point is to check the derived results (R4, R5, R6, R10) empirically and to
answer the question that actually matters -- how aggressive should the Charge be
-- against a *field*, rather than against one opponent.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import median

CAP_MULTIPLE = 4.0  # c >= 4t; the floor is the pessimistic assumption for us


@dataclass
class Team:
    name: str
    policy: str
    sigma: float = 0.35   # log-normal error of this team's Estimate of t
    net: float = 0.0
    income: float = 0.0
    costs: float = 0.0


def quantile(t_hat: float, sigma: float, q: float) -> float:
    """Quantile q of a log-normal posterior centred on t_hat."""
    # inverse standard normal, Acklam-free: good enough via bisection on erf
    lo, hi = -6.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < q:
            lo = mid
        else:
            hi = mid
    return t_hat * math.exp(sigma * (lo + hi) / 2)


def submit(team: Team, t_hat: float, p_accept_hint: float) -> tuple[float, float]:
    """Turn an Estimate into (Charge, Limit) under this team's policy."""
    s = team.sigma
    if team.policy == "dark":
        return 0.0, 0.0
    if team.policy == "naive":                       # a = b = t_hat
        return t_hat, t_hat
    if team.policy == "generous":                    # fears the 1.5a penalty
        return t_hat, quantile(t_hat, s, 0.90)
    if team.policy == "timid":                       # fears everything
        return quantile(t_hat, s, 0.30), quantile(t_hat, s, 0.10)
    if team.policy == "exploiter":                   # parks at the cap
        return CAP_MULTIPLE * t_hat, quantile(t_hat, s, 1 / 3)
    if team.policy == "wireclaim":                   # R5b + R6
        # Charge: maximise a*G(a) + overcharge term. The optimum lands near
        # 0.7*t_hat when nobody accepts an Overcharge, and climbs with p.
        best, best_ev = 0.7 * t_hat, -1.0
        for mult in (0.45, 0.55, 0.65, 0.7, 0.8, 0.9, 1.0, 1.3, 2.0, 3.0, 4.0):
            a = t_hat * mult
            z = math.log(mult) / s
            g = 0.5 * (1 - math.erf(z / math.sqrt(2)))
            ev = a * g + min(a, CAP_MULTIPLE * t_hat) * (1 - g) * p_accept_hint
            if ev > best_ev:
                best, best_ev = a, ev
        # Limit: flat anywhere in the bottom third, so take the middle of it.
        return best, quantile(t_hat, s, 0.20)
    raise ValueError(team.policy)


def play(teams: list[Team], games: int, items: int, dark_from: float | None,
         seed: int = 0, p_accept: float = 0.0) -> None:
    """`p_accept` is the share of the Field expected to accept an Overcharge.

    It defaults to 0 -- i.e. honest -- on purpose. An early version of this file
    estimated it inline from the previous Line Item and got it badly wrong, which
    pushed the Charge above optimum and cost ~60% of net. A mis-measured p is worse
    than no p at all, so this must be supplied from settled-Game data (README R9)
    or left at zero.
    """
    rng = random.Random(seed)
    for g in range(games):
        dark = dark_from is not None and g / games >= dark_from
        subs = []
        for team in teams:
            live = team
            if dark and team.policy in ("naive", "generous", "timid", "exploiter"):
                live = Team(team.name, "dark", team.sigma)  # they went to sleep
            subs.append(live)
        for _ in range(items):
            t = math.exp(rng.gauss(math.log(200), 0.8))     # Fair Value
            c = CAP_MULTIPLE * t
            quotes = []
            for team, live in zip(teams, subs):
                t_hat = t * math.exp(rng.gauss(0, live.sigma))
                quotes.append(submit(live, t_hat, p_accept))
            for i, (a, _) in enumerate(quotes):
                for j, (_, b) in enumerate(quotes):
                    if i == j:
                        continue
                    fair, accepted = a <= t, a <= b
                    if fair and accepted:
                        gain, cost = a, a
                    elif fair:
                        gain, cost = a, 1.5 * a
                    elif accepted:
                        gain = cost = min(a, c)
                    else:
                        gain = cost = 0.0
                    teams[i].income += gain
                    teams[j].costs += cost

    for team in teams:
        team.net = team.income - team.costs


def field(dark_from: float | None) -> list[Team]:
    t: list[Team] = [Team("WireClaim", "wireclaim", 0.30)]
    t += [Team(f"naive{i}", "naive", 0.45) for i in range(12)]
    t += [Team(f"generous{i}", "generous", 0.45) for i in range(8)]
    t += [Team(f"timid{i}", "timid", 0.50) for i in range(6)]
    t += [Team(f"exploit{i}", "exploiter", 0.45) for i in range(4)]
    t += [Team(f"dark{i}", "dark", 0.60) for i in range(4)]
    return t


def report(label: str, teams: list[Team]) -> None:
    print(f"\n=== {label}")
    by_policy: dict[str, list[float]] = {}
    for team in teams:
        by_policy.setdefault(team.policy, []).append(team.net)
    rows = sorted(by_policy.items(), key=lambda kv: -median(kv[1]))
    print(f"{'policy':<12}{'n':>3}{'median net':>14}")
    for policy, nets in rows:
        print(f"{policy:<12}{len(nets):>3}{median(nets):>14,.0f}")
    rank = sorted(teams, key=lambda x: -x.net).index(
        next(t for t in teams if t.name == "WireClaim")) + 1
    print(f"WireClaim rank: {rank}/{len(teams)}")


if __name__ == "__main__":
    for label, dark_from in [("field stays awake all 100 games", None),
                             ("field sleeps from game 43 (README R10)", 0.43)]:
        teams = field(dark_from)
        play(teams, games=100, items=5, dark_from=dark_from, seed=7)
        report(label, teams)
