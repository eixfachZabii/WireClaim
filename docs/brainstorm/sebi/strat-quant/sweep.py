"""Reproduces every number in docs/strat-quant/PLAN.md. Stdlib only: `python3 sweep.py`.

Moves to sim/sweep.py once the package exists; kept here so the plan's claims are
checkable before any code is written.
"""
import math
from math import exp, log, sqrt, pi as PI

Phi = lambda z: 0.5 * (1 + math.erf(z / sqrt(2)))
phi = lambda z: exp(-z * z / 2) / sqrt(2 * PI)


def Phinv(p, lo=-10.0, hi=10.0):
    for _ in range(300):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if Phi(m) < p else (lo, m)
    return (lo + hi) / 2


def zstar(sig, lo=-6.0, hi=6.0):
    """z* solving sig*Phi(-z) = phi(z): the risk-free issuer optimum a* = exp(mu + sig*z*)."""
    for _ in range(300):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if sig * Phi(-m) - phi(m) > 0 else (lo, m)
    return (lo + hi) / 2


# --- t ~ LogNormal(0, SIG^2) i.e. median t_hat normalised to 1 -----------------
G    = lambda a, s: 1 - Phi(log(a) / s)                      # P(t >= a)
def Emin(a, s):                                              # E[min(a,c)], c = 4t (the floor)
    k, lk = a / 4.0, log(a / 4.0)
    return 4 * (exp(s * s / 2) * Phi((lk - s * s) / s) + k * (1 - Phi(lk / s)))


# --- Section 8: risk-free issuer optimum --------------------------------------
print("[PLAN 8, delta-R5b] risk-free issuer optimum (p == 0)")
print(f"{'sigma':>6} {'z*':>7} {'a*/median':>10} {'income':>8} {'vs a=median':>12}")
for s in (0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.80, 1.00):
    z = zstar(s); J = exp(s * z) * Phi(-z)
    print(f"{s:6.2f} {z:7.3f} {exp(s*z):10.3f} {J:8.4f} {100*(J/0.5-1):+11.1f}%")
print(f"  crossover a*=median at sigma = {min((abs(zstar(s/1000)), s/1000) for s in range(700,900))[1]:.3f}\n")

# --- Section 2.1: reviewer policy sweep ---------------------------------------
FIELDS = {
    "saturday (aggressive)": [(.6,.06),(.8,.10),(.9,.10),(1.,.14),(1.1,.10),(1.2,.10),(1.5,.12),(2.,.13),(4.,.15)],
    "baseline":              [(.6,.08),(.8,.14),(.9,.14),(1.,.16),(1.1,.12),(1.2,.10),(1.5,.10),(2.,.10),(4.,.06)],
    "sunday (recalibrated)": [(.6,.12),(.8,.20),(.9,.20),(1.,.20),(1.1,.10),(1.2,.08),(1.5,.05),(2.,.03),(4.,.02)],
}

def reviewer_cost(b, s, field):
    acc = lambda a: G(a, s) * a + (1 - G(a, s)) * Emin(a, s)
    rej = lambda a: 1.5 * a * G(a, s)
    return sum(w * (acc(a) if a <= b else rej(a)) for a, w in field)

print("[PLAN 2.1] reviewer E[cost] per opponent-item, units of t_hat")
for name, field in FIELDS.items():
    print(f"  field: {name}")
    print(f"  {'sigma':>6} {'Q1/3':>8} {'b=0':>17} {'b=median':>17} {'b=Q2/3':>17} {'b=Q0.9':>17}")
    for s in (0.25, 0.30, 0.40, 0.50, 0.60):
        o = reviewer_cost(exp(s * Phinv(1/3)), s, field)
        cells = [reviewer_cost(b, s, field) for b in
                 (0.0, 1.0, exp(s*Phinv(2/3)), exp(s*Phinv(0.9)))]
        print(f"  {s:6.2f} {o:8.4f} " + " ".join(f"{c:8.4f}({100*(c/o-1):+5.1f}%)" for c in cells))
print()

# --- Section 2.2 / 8: issuer optimum against a modelled field ------------------
GRID = [exp(log(0.2) + i * (log(6.0) - log(0.2)) / 799) for i in range(800)]

def issuer(s, w_dark, w_gen, m_gen=6.0):
    """Field b-distribution: a core lognormal + an over-generous minority + dark teams."""
    wc = 1 - w_dark - w_gen
    p = lambda a: wc * (1 - Phi(log(a) / 0.35)) + w_gen * (1 - Phi(log(a / m_gen) / 0.5))
    J = [a * G(a, s) + Emin(a, s) * (1 - G(a, s)) * p(a) for a in GRID]
    i = max(range(len(GRID)), key=lambda i: J[i])
    naive = 1.0 * G(1., s) + Emin(1., s) * (1 - G(1., s)) * p(1.)
    return GRID[i], J[i], naive, p(4.0)

print("[PLAN 2.2] issuer a* vs naive a = t_hat")
print(f"{'sigma':>6} {'field':>26} {'p(4x)':>7} {'a*':>6} {'J(a*)':>7} {'J(naive)':>9} {'edge':>8}")
for s in (0.25, 0.40, 0.60):
    for lbl, wd, wg in (("awake, defensive", .05, .00), ("awake, 25% generous", .05, .25),
                        ("overnight, 55% dark", .55, .05)):
        a, J, n, p4 = issuer(s, wd, wg)
        print(f"{s:6.2f} {lbl:>26} {p4:7.3f} {a:6.2f} {J:7.3f} {n:9.3f} {100*(J/n-1):+7.1f}%")

print("\n[PLAN 8, delta-R5] when does the CAP branch actually win? (sigma=0.40)")
for wg in (i / 100 for i in range(0, 41, 5)):
    a, J, n, p4 = issuer(0.40, 0.05, wg)
    print(f"  generous share={wg:4.2f}  p(4x)={p4:5.3f}  a*={a:5.2f}" + ("   <-- CAP" if a > 2 else ""))

# --- Section 7.1: one missed game, in units of quant edge ---------------------
s, field = 0.40, FIELDS["baseline"]
rev = reviewer_cost(1.0, s, field) - reviewer_cost(exp(s * Phinv(1/3)), s, field)
dark_excess = reviewer_cost(0.0, s, field) - reviewer_cost(exp(s * Phinv(1/3)), s, field)
print("\n[PLAN 7.1] uptime dominates")
for lbl, wd, wg in (("awake", .05, .05), ("overnight", .55, .05)):
    a, J, n, _ = issuer(s, wd, wg)
    edge = rev + (J - n)
    print(f"  {lbl:>10}: quant edge {edge:.4f}/opp-item, missed game {J+dark_excess:.4f}"
          f"  => 1 missed game = {(J+dark_excess)/edge:.1f} games of edge")

# --- Section 2.3: spike-and-slab -----------------------------------------------
print("\n[PLAN 2.3] b = Q1/3 with coverage doubt (sigma=0.40, median 100)")
for p0 in (0.0, 0.05, 0.10, 0.20, 0.30, 0.40):
    b = 0.0 if p0 >= 1/3 else 100 * exp(0.40 * Phinv((1/3 - p0) / (1 - p0)))
    print(f"  pi0={p0:4.2f}  b={b:6.2f}")
