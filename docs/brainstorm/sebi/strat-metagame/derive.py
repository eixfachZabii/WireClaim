"""Derivations behind docs/strat-metagame/PLAN.md (M1-M11). Stdlib only: python3 derive.py"""
from math import log, exp, sqrt
from statistics import NormalDist
N = NormalDist()
Phi = N.cdf; phi = N.pdf

def hazard(z): return phi(z)/(1-Phi(z))

# 1) optimal honest charge with p == 0 : maximise a * P(t>=a), t ~ LogNormal(0, s)
def opt_honest(s):
    lo, hi = -5.0, 5.0
    for _ in range(200):
        mid = (lo+hi)/2
        if hazard(mid) < s: lo = mid
        else: hi = mid
    z = (lo+hi)/2
    a = exp(z*s); G = 1-Phi(z)
    return z, a, G, a*G

print("=== M3: optimal honest charge, p=0 ===")
for s in (0.2,0.3,0.4,0.5,0.6,0.8):
    z,a,G,ev = opt_honest(s)
    print(f"  sigma_p={s:.1f}  z*={z:+.3f}  a/t_hat={a:.3f}  P(a<=t)={G:.3f}  EV/t={ev:.3f}  pct_of_posterior={Phi(z)*100:.1f}%")

# 2) cap-jump break-even : 4t*p > EV_honest
print("\n=== M4: cap-jump break-even p(c) for c=4t and c=6t ===")
for s in (0.2,0.3,0.4,0.5):
    _,_,_,ev = opt_honest(s)
    print(f"  sigma_p={s:.1f}  EV_honest={ev:.3f}t  ->  p(4t)>{ev/4*100:.1f}%   p(6t)>{ev/6*100:.1f}%   (README says 25%)")

# 3) full objective with a field:  EV(a) = a*[G(a) + (1-G(a))*p(a)],  p(a)=rho*S_g(a)
def ev_curve(s_p, m50, s_g, rho, cap=None, grid=None):
    grid = grid or [exp(x/200.0) for x in range(-160, 200)]
    best=(None,-1)
    for a in grid:
        G = 1-Phi(log(a)/s_p)
        p = rho*(1-Phi((log(a)-log(m50))/s_g))
        pay = min(a, cap) if cap else a
        ev = a*G + pay*(1-G)*p
        if ev>best[1]: best=(a,ev)
    return best

print("\n=== M11: value of knowing the field (sigma_p=0.3, sigma_g=0.5, rho=0.85) ===")
base = opt_honest(0.3)
print(f"  field-blind baseline: a={base[1]:.3f}t_hat  EV={base[3]:.3f}t")
for m50 in (0.6,0.8,1.0,1.25,1.5,2.0,2.5,3.0,4.0):
    a,ev = ev_curve(0.3, m50, 0.5, 0.85)
    print(f"  m50={m50:<4} -> a*={a:.3f}t_hat  EV={ev:.3f}t   gain vs blind = {(ev/base[3]-1)*100:+.1f}%")

print("\n  (same, overnight rho=0.50)")
for m50 in (0.8,1.0,1.5,2.0,3.0):
    a,ev = ev_curve(0.3, m50, 0.5, 0.50)
    print(f"  m50={m50:<4} -> a*={a:.3f}t_hat  EV={ev:.3f}t   gain = {(ev/base[3]-1)*100:+.1f}%")

# 4) when does the argmax actually jump to the cap?
print("\n=== when does a* jump past 2x t_hat? (cap c=4t) ===")
for m50 in (1.5,2.0,2.5,3.0,4.0,5.0):
    a,ev = ev_curve(0.3, m50, 0.5, 0.85, cap=4.0)
    S4 = 0.85*(1-Phi((log(4)-log(m50))/0.5))
    print(f"  m50={m50:<4} p(4t)={S4:.3f}  a*={a:.3f}  EV={ev:.3f}  {'CAP JUMP' if a>2 else ''}")

# 5) detection power
print("\n=== M7: detection power, n_teams=34 ===")
n=34
for p in (0.15,0.30,0.50):
    se=sqrt(p*(1-p)/n)
    for d in (0.15,0.25,0.40):
        for games in (1,2,3):
            sep = se/sqrt(games)
            z = d/(sep*sqrt(2))
            if games==1: print(f"  p={p:.2f} se_1game={se:.3f}  delta={d:.2f}: ", end="")
            print(f"{games}g:{z:.2f}sig ", end="")
        print()

# 6) timeline
print("\n=== game -> clock ===")
import datetime
t0 = datetime.datetime(2026,8,22,15,0,0)
for k in (1,5,6,20,22,23,39,40,50,60,72,73,82,85,86,95,100):
    t = t0 + datetime.timedelta(seconds=757.575*(k-1))
    print(f"  G{k:<4} {t.strftime('%a %H:%M')}")
from statistics import NormalDist
N=NormalDist(); Phi=N.cdf

# --- M10: reviewer rule with the cap.  accept iff q > min(a,c)/(min(a,c)+0.5a)
print("=== M10: reviewer accept-bar theta(a) = min(a,c)/(min(a,c)+0.5a),  c = 4*t_hat ===")
c=4.0
for a in (0.5,1.0,2.0,4.0,6.0,10.0,20.0,50.0):
    th = min(a,c)/(min(a,c)+0.5*a)
    q  = 1-Phi(log(a)/0.3)          # covered item, sigma_p=0.3
    print(f"  a={a:>5.1f}t_hat  bar={th:.3f}  q={q:.4f}  -> {'ACCEPT' if q>th else 'reject'}")

print("\n=== M10b: suspected-uncovered item.  P(covered)=pc, t=v if covered, cap floor cf ===")
v=1.0
for pc in (0.2,0.3,0.5):
    for cf in (0.05,0.10,0.25,0.50,1.0):
        # b* = largest a with q(a) > min(a,c_eff)/(min(a,c_eff)+0.5a); c_eff mixes 4v and cf
        best=0
        for i in range(1,400):
            a=i/100.0
            q = pc*(1-Phi(log(a/v)/0.3))
            ceff = pc*4*v + (1-pc)*cf              # expected cap when fraud... use conservative mix
            pay  = pc*min(a,4*v) + (1-pc)*min(a,cf)
            # E[cost|accept] = q*a + (1-q)*E[min(a,c)|fraud];  fraud here == uncovered
            cost_acc = q*a + (1-q)*min(a,cf)
            cost_rej = q*1.5*a
            if cost_acc < cost_rej: best=a
        print(f"  P(covered)={pc}  cap_floor={cf:>4}v  ->  b* = {best:.2f}v   ({'b>0: ACCEPT ZONE' if best>0 else 'b=0'})")

print("\n=== M5: value of the uncovered-item play, per case ===")
# 8 line items, 1.5 uncovered on average, honest EV per covered item = 0.623*v
for kappa in (0.10,0.20,0.30,0.40):
    for cf in (0.25,0.5,1.0):
        honest = 6.5*0.623
        extra  = 1.5*min(1.0,cf)*kappa
        print(f"  kappa={kappa:.2f} cap_floor={cf:>4}v  honest={honest:.2f}v  +uncovered={extra:.2f}v  => {extra/honest*100:+.1f}%")

print("\n=== M2: rank-vs-absolute break-even, N teams ===")
for Nt in (2,5,10,20,35,60):
    for pt in (0.0,0.8):
        bar = (Nt + 0.5 - 0.5*pt)/(4*Nt)
        print(f"  N={Nt:<3} p(t)={pt}  rank break-even p(c) = {bar*100:.2f}%", end="   ")
    print()
