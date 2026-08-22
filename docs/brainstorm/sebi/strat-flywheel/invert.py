"""Numerics and reference implementation behind docs/strat-flywheel/PLAN.md (F1-F8).

Stdlib only, no deps:   python3 docs/strat-flywheel/invert.py

  SECTION 1  settle()        the payoff matrix (README section 2) as code
  SECTION 2  invert_item()   the R9 inversion: Transaction rows -> t bracket, every
                             Charge, every Limit, the Cap.  This is the production algorithm.
  SECTION 3  round-trip      generate a settled Game from known truth, recover it, assert
  SECTION 4  F1  how tight is one Game's label, by phase -- and in the fallback
  SECTION 5  F2  uncovered-item (t == 0) detection accuracy
  SECTION 6  F3  what bias-correction and width-calibration are each worth, in money
  SECTION 7  F4  the compounding curve: posterior sd at Game 1 / 20 / 50 / 90
  SECTION 8  F5  how much of the calibration curve survives interval censoring
  SECTION 9  F6  censored MLE convergence: full Field vs own-rows-only fallback
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist, median

N = NormalDist()
Phi, phi, INV = N.cdf, N.pdf, N.inv_cdf

CAP_FLOOR = 50.0      # hypothesised absolute floor on c; we DISCOVER it, never assume it
CAP_MULT = 4.0        # c >= 4t, guaranteed by the rules
EPS = 1e-9


# ─────────────────────────── SECTION 1 · the rules ───────────────────────────

def settle(a, b, t, c):
    """One Transaction -> (accepted, amount the Reviewer pays).

    min(a,c) == a whenever a <= t, because c >= 4t >= 4a.
    THE CAP CAN ONLY EVER BIND ON A FRAUD-ZONE CHARGE.  That is load-bearing below.
    """
    if a <= b:
        return True, (a if a <= t else min(a, c))
    return False, (1.5 * a if a <= t else 0.0)


# ───────────────────────── SECTION 2 · the inversion ─────────────────────────

class IssuerEvidence:
    __slots__ = ("issuer", "a_exact", "a_lower", "verdict", "n_acc", "n_rej", "capped")

    def __init__(self, issuer):
        self.issuer, self.a_exact, self.a_lower = issuer, None, 0.0
        self.verdict, self.n_acc, self.n_rej, self.capped = "UNKNOWN", 0, 0, False


class ItemInversion:
    def __init__(self):
        self.t_lo = 0.0                 # proven  t >= t_lo
        self.t_hi = math.inf            # proven  t <  t_hi   (or <= if t_hi_closed)
        self.t_hi_closed = False
        self.cap = None
        self.zero_t = False
        self.n_rej_zero = 0
        self.issuers, self.b_bracket = {}, {}
        self.guttman_violations = 0
        self.n_fair = self.n_fraud = 0

    def contains(self, t):
        hi_ok = (t <= self.t_hi + EPS) if self.t_hi_closed else (t < self.t_hi + EPS)
        return self.t_lo - EPS <= t and hi_ok

    @property
    def two_sided(self):
        return self.t_lo > 0 and math.isfinite(self.t_hi) and self.t_hi > self.t_lo

    @property
    def log_width(self):
        return math.log(self.t_hi / self.t_lo) if self.two_sided else math.inf


def invert_item(rows, known_a=None, lawyer=1.5):
    """rows: (issuer, reviewer, accepted: bool, amount: float) for ONE Line Item.

    `known_a` injects Charges we know without inference -- in practice exactly one entry,
    our own, read from our Submission log.  It is what makes the fallback (section 6) work.
    """
    out, by_issuer = ItemInversion(), {}
    for iss, rev, acc, amt in rows:
        by_issuer.setdefault(iss, []).append((rev, acc, amt))

    # ── pass 1 · per-issuer local evidence ────────────────────────────────
    for iss, rs in by_issuer.items():
        ev = IssuerEvidence(iss)
        fair_vals, acc_amts, zero_rej = [], [], False
        for rev, acc, amt in rs:
            if acc:
                ev.n_acc += 1
                acc_amts.append(amt)
            else:
                ev.n_rej += 1
                if amt > 0:
                    fair_vals.append(amt / lawyer)      # wrongful rejection => a <= t
                else:
                    zero_rej = True                     # rightful rejection  => a >  t
                    out.n_rej_zero += 1
        if fair_vals:
            ev.a_exact, ev.verdict = median(fair_vals), "FAIR"
            out.n_fair += 1
        elif zero_rej:
            ev.verdict = "FRAUD"
            out.n_fraud += 1
        if acc_amts:
            ev.a_lower = max(acc_amts)                  # == min(a,c), identical across reviewers
            if ev.a_lower == 0.0:
                ev.a_exact = 0.0                        # min(a,c)=0 and c>0  =>  a == 0 (dark)
        if known_a and iss in known_a:
            ev.a_exact = known_a[iss]
        out.issuers[iss] = ev

    # ── pass 2 · t_lo, from the largest proven-fair Charge ────────────────
    fair_as = [e.a_exact for e in out.issuers.values()
               if e.verdict == "FAIR" and e.a_exact is not None]
    out.t_lo = max(fair_as) if fair_as else 0.0

    # ── pass 3 · the Cap.  c is shared across teams on this Line Item, so two DISTINCT
    #   issuers paying out the identical maximal amount is measure-zero unless both capped.
    payouts = {}
    for iss, e in out.issuers.items():
        if e.a_lower > 0:
            payouts.setdefault(round(e.a_lower, 6), []).append((iss, e.a_lower))
    if payouts:
        kmax = max(payouts)
        grp = payouts[kmax]
        distinct_a = {e.a_exact for i, e in out.issuers.items()
                      if any(i == g[0] for g in grp) and e.a_exact is not None}
        if len(grp) >= 2 and kmax >= CAP_MULT * out.t_lo and len(distinct_a) <= 1:
            out.cap = max(v for _, v in grp)      # FULL precision: c/4 amplifies rounding
            for iss, _ in grp:
                out.issuers[iss].capped = True

    # ── pass 4 · the uncapping lemma ──────────────────────────────────────
    #   c >= 4t >= 4*t_lo, so a payout strictly below 4*t_lo cannot be the Cap and is
    #   therefore the Charge itself, exactly.  If the Cap is known, the test is exact.
    bar = out.cap if out.cap is not None else CAP_MULT * out.t_lo
    for e in out.issuers.values():
        if e.a_exact is None and e.a_lower > 0 and not e.capped and e.a_lower < bar:
            e.a_exact = e.a_lower

    # ── pass 5 · t_hi, from fraud witnesses ───────────────────────────────
    #   any fraud witness with >= 1 acceptance:  t < a  and  a >= a_lower
    #     uncapped: a_lower == a        =>  t <  a_lower       (strict)
    #     capped  : a_lower == c >= 4t  =>  t <= a_lower / 4    (four times tighter, closed)
    #   t < a_lower is therefore always safe; confirming the Cap sharpens it 4x.
    ubs = []
    for e in out.issuers.values():
        if e.verdict == "FRAUD":
            if e.a_exact is not None and not e.capped:
                ubs.append((e.a_exact, False))
            elif e.a_lower > 0:
                ubs.append((e.a_lower / CAP_MULT, True) if e.capped else (e.a_lower, False))
    if out.cap is not None:
        ubs.append((out.cap / CAP_MULT, True))          # c >= 4t  =>  t <= c/4, always
    if ubs:
        best = min(ubs, key=lambda z: (z[0], not z[1]))
        out.t_hi, out.t_hi_closed = best

    # ── pass 6 · every Reviewer's Limit, and the Guttman check ────────────
    by_rev = {}
    for iss, rs in by_issuer.items():
        a = out.issuers[iss].a_exact
        if a is None:
            continue
        for rev, acc, amt in rs:
            by_rev.setdefault(rev, []).append((a, acc))
    for rev, obs in by_rev.items():
        lo = max([a for a, acc in obs if acc], default=0.0)
        hi = min([a for a, acc in obs if not acc], default=math.inf)
        out.b_bracket[rev] = (lo, hi)
        if lo > hi + EPS:
            out.guttman_violations += 1   # accepted a HIGHER Charge than one it rejected:
                                          # impossible under one Limit per Line Item (R3)

    # ── pass 7 · uncovered detection.  If t > 0 then somebody charges in (0, t] and
    #   somebody rejects them, so at least one rejected row carries amount > 0.
    out.zero_t = (out.n_fair == 0 and out.n_rej_zero >= 3)
    return out


# ─────────────────── SECTION 3 · synthetic Game + round trip ──────────────────

def lognorm_q(t_hat, sigma, q):
    return t_hat * math.exp(sigma * INV(q))


def opt_honest_z(sigma):
    """z* with hazard(z)=sigma; risk-free optimal Charge is t_hat*exp(sigma*z*)  (R5b)."""
    lo, hi = -6.0, 6.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if phi(mid) / (1 - Phi(mid)) < sigma:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


_Z_CACHE = {}


def z_of(sigma):
    k = round(sigma, 4)
    if k not in _Z_CACHE:
        _Z_CACHE[k] = opt_honest_z(k)
    return _Z_CACHE[k]


def team_submit(policy, t_hat, sigma, cap_guess):
    if policy == "dark":
        return 0.0, 0.0
    if policy == "naive":
        return t_hat, t_hat
    if policy == "timid":
        return lognorm_q(t_hat, sigma, 0.20), lognorm_q(t_hat, sigma, 0.10)
    if policy == "generous":
        return lognorm_q(t_hat, sigma, 0.40), lognorm_q(t_hat, sigma, 0.90)
    if policy == "exploiter":
        return cap_guess, lognorm_q(t_hat, sigma, 1 / 3)
    if policy == "sloppy":                    # units / VAT / gross-vs-net error: 1.3x high
        return 1.3 * t_hat, 1.3 * t_hat
    return t_hat * math.exp(sigma * z_of(sigma)), lognorm_q(t_hat, sigma, 1 / 3)


US = "T29"


def make_game(rng, n_teams=30, dark_share=0.0, pi0=0.15, tau=0.8, med=300.0,
              our_beta=None, our_sigma_true=None, our_sigma_belief=None, our_beta_known=0.0,
              our_a_ratio=None, our_b_q=1 / 3, shrink=True):
    """One Line Item played by n_teams.  Returns (t, c, subs, rows, ours) where
    subs[name] = (a, b, policy) and ours = (a, b, t_hat)."""
    uncovered = rng.random() < pi0
    t = 0.0 if uncovered else med * math.exp(rng.gauss(0, tau))
    c = max(CAP_MULT * t, CAP_FLOOR)
    n_dark = int(round(dark_share * n_teams))
    subs, ours = {}, None
    for i in range(n_teams):
        name = f"T{i:02d}"
        anchor = t if t > 0 else med * math.exp(rng.gauss(0, tau))
        if name == US and our_sigma_true is not None:
            t_hat = anchor * math.exp(rng.gauss(our_beta, our_sigma_true)) * math.exp(-our_beta_known)
            sb = our_sigma_belief
            if shrink:
                w = tau ** 2 / (tau ** 2 + sb ** 2)                 # R6b shrinkage
                t_hat = med * (t_hat / med) ** w
            a = t_hat * (our_a_ratio if our_a_ratio else math.exp(sb * z_of(sb)))
            b = lognorm_q(t_hat, sb, our_b_q)
            subs[name], ours = (a, b, "us"), (a, b, t_hat)
            continue
        pol = "dark" if i < n_dark else rng.choices(
            ("naive", "timid", "calibrated", "generous", "exploiter", "sloppy"),
            weights=(22, 12, 30, 20, 6, 10))[0]
        sig = rng.uniform(0.30, 0.60)
        t_hat = anchor * math.exp(rng.gauss(0, sig))
        subs[name] = team_submit(pol, t_hat, sig, CAP_MULT * t_hat) + (pol,)
    rows = []
    for iss, (a, _, _) in subs.items():
        for rev, (_, b, _) in subs.items():
            if iss != rev:
                acc, amt = settle(a, b, t, c)
                rows.append((iss, rev, acc, amt))
    return t, c, subs, rows, ours


def own_rows(rows, us=US):
    return [r for r in rows if r[0] == us or r[1] == us]


def roundtrip_test(trials=600, seed=7):
    rng = random.Random(seed)
    bad_bracket = bad_a = bad_b = bad_cap = guttman = 0
    a_rec = a_tot = cap_found = cap_possible = 0
    for _ in range(trials):
        t, c, subs, rows, _ = make_game(rng, dark_share=rng.choice((0.0, 0.2, 0.5, 0.8)))
        inv = invert_item(rows)
        if not inv.contains(t):
            bad_bracket += 1
        for name, (a, b, _) in subs.items():
            e = inv.issuers[name]
            a_tot += 1
            if e.a_exact is not None:
                a_rec += 1
                if abs(e.a_exact - a) > 1e-6:
                    bad_a += 1
            lo, hi = inv.b_bracket.get(name, (0.0, math.inf))
            if not (lo - EPS <= b < hi + EPS):
                bad_b += 1
        if any(x[0] > c for x in [(v[0],) for v in subs.values()]):
            cap_possible += 1
        if inv.cap is not None:
            cap_found += 1
            if abs(inv.cap - c) > 1e-6:
                bad_cap += 1
        guttman += inv.guttman_violations
    print("=== SECTION 3 · round-trip on synthetic settled Games ===")
    print(f"  trials {trials}, 30 teams, 0-80% dark")
    print(f"  t outside recovered bracket      {bad_bracket:>5}   (must be 0)")
    print(f"  Charge recovered EXACTLY         {a_rec}/{a_tot} = {a_rec/a_tot:.1%}")
    print(f"  Charge recovered WRONG           {bad_a:>5}   (must be 0)")
    print(f"  Limit outside its bracket        {bad_b:>5}   (must be 0)")
    print(f"  Cap detected / detectable        {cap_found}/{cap_possible}   wrong: {bad_cap} (must be 0)")
    print(f"  Guttman violations               {guttman:>5}   (must be 0; >0 = our model of the game is wrong)")


# ───────────────── SECTION 4 · F1 bracket width, and the fallback ─────────────

def f1_bracket(trials=2500, seed=11):
    print("\n=== SECTION 4 · F1 how tight is ONE Game's label? ===")
    print("  bracket = [max proven-fair Charge, min proven-fraud Charge); covered items only")
    print(f"  {'regime':30} {'2-sided':>8} {'1-sided lo':>11} {'p50 width':>10} {'p50 +-':>8} "
          f"{'p90 +-':>8} {'p50 t/L':>8}")
    for label, dark, scope in (
        ("Sat 15:00-00:00, Field awake", 0.00, "all"),
        ("Sun 00:00-08:00, 50% dark", 0.50, "all"),
        ("Sun 03:00, 80% dark", 0.80, "all"),
        ("FALLBACK own rows, awake", 0.00, "own"),
        ("FALLBACK own rows, 50% dark", 0.50, "own"),
    ):
        rng = random.Random(seed)
        widths, two, onesided, n, gaps = [], 0, 0, 0, []
        for _ in range(trials):
            t, c, subs, rows, ours = make_game(
                rng, dark_share=dark, our_beta=0.18, our_sigma_true=0.45, our_sigma_belief=0.30)
            if t == 0:
                continue
            n += 1
            inv = (invert_item(rows) if scope == "all"
                   else invert_item(own_rows(rows), known_a={US: ours[0]}))
            if inv.two_sided:
                two += 1
                widths.append(inv.log_width)
            elif inv.t_lo > 0:
                onesided += 1
            if inv.t_lo > 0:
                gaps.append(t / inv.t_lo)
        widths.sort(); gaps.sort()
        p50 = widths[len(widths) // 2] if widths else float("nan")
        p90 = widths[int(0.9 * len(widths))] if widths else float("nan")
        g50 = gaps[len(gaps) // 2] if gaps else float('nan')
        print(f"  {label:30} {two/n:>7.1%} {onesided/n:>10.1%} {p50:>10.3f} "
              f"{100*(math.exp(p50/2)-1):>7.1f}% {100*(math.exp(p90/2)-1):>7.1f}% {g50:>8.3f}")
    print("  '+-' is the half-width as a percentage: log width 0.10 pins t to a +-5% band.")


# ─────────────── SECTION 5 · F2 uncovered-item detection (t == 0) ─────────────

def f2_coverage(trials=4000, seed=13):
    print("\n=== SECTION 5 · F2 uncovered-item detection (t == 0) ===")
    print("  rule: no rejected row anywhere carries amount > 0, and >= 3 rightful rejections seen")
    for label, dark, scope in (("Field-wide, awake", 0.0, "all"),
                               ("Field-wide, 50% dark", 0.5, "all"),
                               ("FALLBACK own rows, awake", 0.0, "own"),
                               ("FALLBACK own rows, 50% dark", 0.5, "own")):
        rng = random.Random(seed)
        tp = fp = fn = tn = 0
        for _ in range(trials):
            t, c, subs, rows, ours = make_game(
                rng, dark_share=dark, our_beta=0.18, our_sigma_true=0.45, our_sigma_belief=0.30)
            inv = (invert_item(rows) if scope == "all"
                   else invert_item(own_rows(rows), known_a={US: ours[0]}))
            if t == 0 and inv.zero_t: tp += 1
            elif t == 0: fn += 1
            elif inv.zero_t: fp += 1
            else: tn += 1
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        print(f"  {label:28} precision {prec:>6.1%}  recall {rec:>6.1%}   "
              f"false 't=0' on a covered item: {fp}/{tn+fp}")


# ─────────────── SECTION 6 · F3 what each learning channel is worth ───────────

def evaluate(rng, trials, beta_known, sigma_belief, dark_share=0.0,
             beta_true=0.18, sigma_true=0.45, n_teams=30, our_a_ratio=None, our_b_q=1 / 3):
    income = costs = tsum = 0.0
    for _ in range(trials):
        t, c, subs, rows, ours = make_game(
            rng, n_teams=n_teams, dark_share=dark_share, our_beta=beta_true,
            our_sigma_true=sigma_true, our_sigma_belief=sigma_belief,
            our_beta_known=beta_known, our_a_ratio=our_a_ratio, our_b_q=our_b_q)
        a, b, _ = ours
        tsum += t
        for name, (aj, bj, _) in subs.items():
            if name == US:
                continue
            acc, _ = settle(a, bj, t, c)
            income += a if a <= t else (min(a, c) if acc else 0.0)   # us as Issuer
            _, paid = settle(aj, b, t, c)                            # us as Reviewer
            costs += paid
    k = n_teams - 1
    return (income - costs) / tsum / k, income / tsum / k, costs / tsum / k


def f3_money(trials=3000, seed=17):
    print("\n=== SECTION 6 · F3 the money value of each learning channel ===")
    print("  truth: estimator log-bias beta=+0.18 (units/VAT-shaped), true sd=0.45.")
    print("  The ensemble self-reports sd 0.22 -- the classic overconfident LLM.")
    print("  Units: per opponent, per unit of true Fair Value summed over covered Line Items.")
    print("  Note R2: net is a small difference of two large numbers. Read the DELTA column.")
    states = [("G1   biased AND overconfident", 0.00, 0.22),
              ("     bias corrected only", 0.18, 0.22),
              ("     width calibrated only", 0.00, 0.45),
              ("G20+ both -- the flywheel", 0.18, 0.45)]
    for phase, dark in (("Field awake (Sat, R10 phase 1)", 0.0),
                        ("60% dark (overnight, R10 phase 2)", 0.6)):
        print(f"\n  --- {phase} ---")
        print(f"  {'our state':34} {'net':>8} {'income':>8} {'costs':>8} {'d(net)':>8} {'as % of income':>15}")
        base = None
        for label, bk, sb in states:
            rng = random.Random(seed)
            net, inc, cost = evaluate(rng, trials, bk, sb, dark_share=dark)
            if base is None:
                base, base_inc = net, inc
                print(f"  {label:34} {net:>8.4f} {inc:>8.4f} {cost:>8.4f} {'--':>8} {'--':>15}")
            else:
                print(f"  {label:34} {net:>8.4f} {inc:>8.4f} {cost:>8.4f} {net-base:>+8.4f} "
                      f"{100*(net-base)/base_inc:>+14.1f}%")
    print("\n  Read the third row against the fourth: correcting the WIDTH while leaving the BIAS")
    print("  in place scores as well as correcting both, because a +0.18 log-bias and a 2x-too-")
    print("  narrow posterior happen to cancel at the Limit. Two wrongs, one right answer.")
    print("  That is the whole argument for fitting on REALISED NET, not on likelihood.")


# ───────────────── SECTION 7 · F4 the compounding curve ──────────────────────

def f4_compounding(items_per_game=8, K_cat=12, sig_eta=0.25, sig_xi=0.34, beta0=0.18,
                   bracket_sd=0.021):
    print("\n=== SECTION 7 · F4 posterior sd vs Game number ===")
    print(f"  ln t_hat = ln t + beta + eta_k + xi   beta0={beta0}  sd(eta)={sig_eta}  "
          f"sd(xi)={sig_xi}  K={K_cat} trades")
    print(f"  {items_per_game} labels/Game; bracket measurement sd {bracket_sd} "
          f"(F1 p50 width/sqrt12 -- negligible next to xi)")
    print(f"  {'Game':>5} {'labels':>7} {'/trade':>7} {'sd(beta)':>9} {'sd(eta)':>8} "
          f"{'sigma':>7} {'vs G1':>6} {'E[inc]/t':>9} {'vs G1':>7}")
    sig1 = ev1 = None
    for g in (1, 3, 5, 10, 20, 35, 50, 70, 90, 100):
        n = max(0, g - 1) * items_per_game
        nk = n / K_cat
        resid = sig_eta ** 2 + sig_xi ** 2 + bracket_sd ** 2
        v_beta = beta0 ** 2 if n == 0 else resid / n
        v_eta = sig_eta ** 2 if nk == 0 else 1.0 / (1.0 / sig_eta ** 2 + nk / sig_xi ** 2)
        sig = math.sqrt(v_beta + v_eta + sig_xi ** 2 + bracket_sd ** 2)
        z = z_of(sig)
        ev = math.exp(sig * z) * (1 - Phi(z))
        if sig1 is None:
            sig1, ev1 = sig, ev
        print(f"  {g:>5} {n:>7} {nk:>7.1f} {math.sqrt(v_beta):>9.3f} {math.sqrt(v_eta):>8.3f} "
              f"{sig:>7.3f} {sig/sig1:>5.0%} {ev:>9.3f} {100*(ev/ev1-1):>+6.1f}%")
    print("\n  plus the exact-item memory channel (recurrence rate r; a re-seen item's bracket")
    print("  truncates its own prior, collapsing sd to ~0.03):")
    print(f"  {'r':>6} {'sd G20':>8} {'sd G50':>8} {'sd G90':>8} {'E[inc] G90':>11} {'vs r=0':>8}")
    base = None
    for r in (0.0, 0.10, 0.25, 0.50):
        cells = []
        for g in (20, 50, 90):
            n, nk = (g - 1) * items_per_game, (g - 1) * items_per_game / K_cat
            resid = sig_eta ** 2 + sig_xi ** 2 + bracket_sd ** 2
            v_beta, v_eta = resid / n, 1.0 / (1.0 / sig_eta ** 2 + nk / sig_xi ** 2)
            sig = math.sqrt(v_beta + v_eta + sig_xi ** 2 + bracket_sd ** 2)
            cells.append(math.sqrt((1 - r) * sig ** 2 + r * 0.03 ** 2))
        z = z_of(cells[-1])
        ev = math.exp(cells[-1] * z) * (1 - Phi(z))
        base = base or ev
        print(f"  {r:>6.0%} {cells[0]:>8.3f} {cells[1]:>8.3f} {cells[2]:>8.3f} {ev:>11.3f} "
              f"{100*(ev/base-1):>+7.1f}%")


# ───────────── SECTION 8 · F5 the identified calibration band ─────────────────

def f5_pit_band(trials=4000, seed=23, sigma_belief=0.30):
    print("\n=== SECTION 8 · F5 how much of the calibration curve survives censoring? ===")
    print("  the hit indicator 1{t <= F^-1(tau)} is KNOWN unless tau lands inside [F(L), F(U))")
    print("  C_lo/C_hi are the sharp bounds on realised coverage; 'band' is what censoring hides")
    for label, dark in (("Field awake", 0.0), ("50% dark", 0.5)):
        rng = random.Random(seed)
        pits = []
        for _ in range(trials):
            t, c, subs, rows, ours = make_game(
                rng, dark_share=dark, our_beta=0.0, our_sigma_true=sigma_belief,
                our_sigma_belief=sigma_belief)
            if t == 0:
                continue
            inv = invert_item(rows)
            if not inv.two_sided:
                continue
            th = ours[2]
            f = lambda x: Phi(math.log(x / th) / sigma_belief) if x > 0 else 0.0
            pits.append((f(inv.t_lo), f(inv.t_hi)))
        n = len(pits)
        print(f"\n  {label}: {n} usable items")
        print(f"  {'tau':>6} {'C_lo':>8} {'C_hi':>8} {'band':>8}")
        for tau in (0.10, 0.20, 1 / 3, 0.50, 0.90):
            lo = sum(1 for a, b in pits if b <= tau) / n
            hi = sum(1 for a, b in pits if a <= tau) / n
            print(f"  {tau:>6.3f} {lo:>8.3f} {hi:>8.3f} {hi-lo:>8.3f}")
        print(f"  mean PIT-interval width {sum(b-a for a,b in pits)/n:.3f} "
              f"= the fraction of items ambiguous at any single tau")


# ───────── SECTION 9 · F6 the fallback: Fisher information, honestly ─────────

def info_exact(sigma):
    """Per-label Fisher information for (beta, sigma) from an EXACTLY observed ln t."""
    return [[1 / sigma ** 2, 0.0], [0.0, 2 / sigma ** 2]]


def info_bracket(sigma, w, trials=40000, seed=31):
    """Per-label information from an interval label of log-width w containing ln t."""
    rng = random.Random(seed)
    I = [[0.0, 0.0], [0.0, 0.0]]
    for _ in range(trials):
        e = rng.gauss(0, 1)                       # (ln t - ln t_hat + beta)/sigma
        nu = rng.random()
        zL, zU = e - w * nu / sigma, e + w * (1 - nu) / sigma
        g = Phi(zU) - Phi(zL)
        if g < 1e-12:
            continue
        db = (phi(zU) - phi(zL)) / sigma / g
        ds = (-phi(zU) * zU + phi(zL) * zL) / sigma / g
        I[0][0] += db * db; I[0][1] += db * ds; I[1][0] += db * ds; I[1][1] += ds * ds
    return [[x / trials for x in row] for row in I]


def info_probit(sigma, ratios, weights=None):
    """Per-label information from the binary outcome 1{our Charge was in the Fair Zone}
    at design points a/t_hat = r.  Zero information about sigma unless the r's differ."""
    weights = weights or [1.0] * len(ratios)
    tw = sum(weights)
    I = [[0.0, 0.0], [0.0, 0.0]]
    for r, wt in zip(ratios, weights):
        u = math.log(r) / sigma
        P = 1 - Phi(u)
        if P <= 1e-9 or P >= 1 - 1e-9:
            continue
        k = phi(u) ** 2 / (sigma ** 2 * P * (1 - P)) * wt / tw
        I[0][0] += k; I[0][1] += -k * u; I[1][0] += -k * u; I[1][1] += k * u * u
    return I


def se_from(I, n):
    det = I[0][0] * I[1][1] - I[0][1] * I[1][0]
    if abs(det) < 1e-12:
        return float("inf"), float("inf")
    return math.sqrt(I[1][1] / det / n), math.sqrt(I[0][0] / det / n)


def f6_fallback(sigma=0.45, items=8):
    print("\n=== SECTION 9 · F6 the no-leaderboard fallback, priced in Fisher information ===")
    print(f"  true posterior sd {sigma}.  Targets: se(beta) <= 0.05, se(sigma) <= 0.045 (10%).")
    print(f"  {items} Line Items per Game.")
    designs = [
        ("T-A field-wide bracket, awake (w=0.07)", info_bracket(sigma, 0.069)),
        ("T-A field-wide bracket, 50% dark (0.14)", info_bracket(sigma, 0.138)),
        ("T-A field-wide bracket, 80% dark (0.32)", info_bracket(sigma, 0.318)),
        ("  (reference) exact ln t observed", info_exact(sigma)),
        ("T-C own bit, NO dispersion a=0.75t_hat", info_probit(sigma, [0.75])),
        ("T-C own bit, mild spread .65-.95", info_probit(sigma, [0.65, 0.75, 0.85, 0.95])),
        ("T-C own bit, designed spread .5-1.4", info_probit(sigma, [0.5, 0.65, 0.8, 1.0, 1.2, 1.4])),
        ("T-C own bit, 80% at opt + 20% probe",
         info_probit(sigma, [0.75, 0.5, 0.65, 0.8, 1.0, 1.2, 1.4],
                     [0.80, 0.033, 0.033, 0.033, 0.033, 0.033, 0.033])),
    ]
    print(f"  {'label source':42} {'I_bb':>8} {'I_ss':>8} {'games->beta':>12} {'games->sigma':>13}")
    for name, I in designs:
        gb = gs = float("inf")
        for n in range(1, 40001):
            sb, ss = se_from(I, n)
            if gb == float("inf") and sb <= 0.05:
                gb = n / items
            if gs == float("inf") and ss <= 0.045:
                gs = n / items
            if gb < float("inf") and gs < float("inf"):
                break
        f = lambda x: "  never" if x == float("inf") else f"{x:6.1f}"
        print(f"  {name:42} {I[0][0]:>8.2f} {I[1][1]:>8.2f} {f(gb):>12} {f(gs):>13}")
    print("\n  The bracket label is 0.07/0.45 = 15% of a posterior sd wide, so censoring costs")
    print("  almost nothing: it is a point label in all but name.")
    f6b_misspecified()


def fit_beta_gamma(labels, sigma_raw):
    """Grid MLE of (beta, gamma) on interval-censored bracket mass -- strat-quant section 3.2."""
    best, arg = -1e18, (0.0, 1.0)
    for bi in range(-30, 31):
        beta = bi * 0.02
        for gi in range(6, 61):
            gam, s2 = gi * 0.05, gi * 0.05 * sigma_raw
            ll = 0.0
            for lth, lL, lU in labels:
                hi = 1.0 if lU == math.inf else Phi((lU - lth + beta) / s2)
                lo = 0.0 if lL == -math.inf else Phi((lL - lth + beta) / s2)
                ll += math.log(max(hi - lo, 1e-12))
            if ll > best:
                best, arg = ll, (beta, gam)
    return arg


def f6b_misspecified(seed=29, beta_true=0.18, sigma_true=0.45, sigma_raw=0.22, items=8,
                     games=60):
    """The SAME likelihood, run on Field-wide brackets vs on own-only bounds."""
    print("\n  --- F6b: what happens if we just feed the fallback's bounds to the same MLE ---")
    rng = random.Random(seed)
    lab_all, lab_own = [], []
    marks = (5, 10, 20, 40, 60)
    print(f"  {'after games':>12}   {'FIELD-WIDE beta/gamma':>24}   {'OWN-ONLY beta/gamma':>24}")
    for g in range(1, games + 1):
        for _ in range(items):
            t, c, subs, rows, ours = make_game(
                rng, dark_share=0.0 if g < 20 else 0.5, our_beta=beta_true,
                our_sigma_true=sigma_true, our_sigma_belief=sigma_raw, shrink=False)
            if t == 0:
                continue
            lth = math.log(ours[2])
            for scope, bucket in (("all", lab_all), ("own", lab_own)):
                inv = (invert_item(rows) if scope == "all"
                       else invert_item(own_rows(rows), known_a={US: ours[0]}))
                lL = math.log(inv.t_lo) if inv.t_lo > 0 else -math.inf
                lU = math.log(inv.t_hi) if math.isfinite(inv.t_hi) else math.inf
                if lL != -math.inf or lU != math.inf:
                    bucket.append((lth, lL, lU))
        if g in marks:
            ba, ga = fit_beta_gamma(lab_all[-500:], sigma_raw)
            bo, go = fit_beta_gamma(lab_own[-500:], sigma_raw)
            print(f"  {g:>12}   {ba:>11.3f}{ga:>13.2f}   {bo:>11.3f}{go:>13.2f}")
    print(f"  {'TRUTH':>12}   {beta_true:>11.3f}{sigma_true/sigma_raw:>13.2f}"
          f"   {beta_true:>11.3f}{sigma_true/sigma_raw:>13.2f}")
    print("  Field-wide converges. Own-only does NOT: the bound we happen to observe is")
    print("  determined by whether our own Estimate was high or low, so the censoring is")
    print("  INFORMATIVE and this likelihood is misspecified. Use the probit instead.")


def f7_straddle(trials=3000, seed=37, sigma_true=0.45, sigma_belief=0.30, beta_true=0.18):
    print("\n=== SECTION 10 · F7 the straddle: manufacturing two-sided labels without the Field ===")
    print("  THEOREM. Own rows alone can never bracket t two-sided while a <= b.")
    print("    a fair witness among the issuers we rejected requires some a_j in (b, t]  => b < t")
    print("    our own Charge being a fraud witness requires a > t")
    print("    a <= b and a > t force b >= a > t, contradiction.  Hence: never both.  QED")
    print("  So the fallback must deliberately open a gap b < a and hope t lands inside it.")
    print(f"  {'design (a/t_hat, b quantile)':32} {'2-sided':>8} {'p50 +-':>8} {'net':>9} {'vs base':>9}")
    base = None
    for a_ratio, b_q in ((None, 1 / 3), (None, 0.10), (0.90, 0.10), (1.00, 0.05),
                         (1.15, 0.05), (1.30, 0.02)):
        rng = random.Random(seed)
        two, n, widths = 0, 0, []
        for _ in range(trials):
            t, c, subs, rows, ours = make_game(
                rng, dark_share=0.3, our_beta=beta_true, our_sigma_true=sigma_true,
                our_sigma_belief=sigma_belief, our_a_ratio=a_ratio, our_b_q=b_q)
            if t == 0:
                continue
            n += 1
            inv = invert_item(own_rows(rows), known_a={US: ours[0]})
            if inv.two_sided:
                two += 1
                widths.append(inv.log_width)
        widths.sort()
        p50 = widths[len(widths) // 2] if widths else float("nan")
        rng = random.Random(seed + 1)
        net, inc, cost = evaluate(rng, trials, 0.18, sigma_belief, dark_share=0.3,
                                  our_a_ratio=a_ratio, our_b_q=b_q)
        base = net if base is None else base
        lab = f"{'R5b opt' if a_ratio is None else a_ratio}, Q{b_q:.2f}"
        print(f"  {lab:32} {two/n:>7.1%} {100*(math.exp(p50/2)-1):>7.1f}% {net:>9.4f} "
              f"{100*(net/base-1):>+8.1f}%")
    print("  Row 1 is the deployed policy and confirms the theorem: 0.0% two-sided.")


if __name__ == "__main__":
    roundtrip_test()
    f1_bracket()
    f2_coverage()
    f3_money()
    f4_compounding()
    f5_pit_band()
    f6_fallback()
    f7_straddle()
