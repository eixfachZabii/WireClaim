import math
from math import exp, log, sqrt
def Phi(x): return 0.5*(1+math.erf(x/sqrt(2)))
def phi(x): return exp(-x*x/2)/sqrt(2*math.pi)

# --- issuer income per opponent, posterior on t lognormal(median m=t, log-sd s)
# a = m*exp(-k s); E = a * P(t>=a) = m exp(-k s) Phi(k); optimum lambda(k)=s
def best_k(s):
    lo,hi=-4.0,6.0
    for _ in range(200):
        mid=(lo+hi)/2
        if phi(mid)/Phi(mid) > s: lo=mid
        else: hi=mid
    return (lo+hi)/2
def income(s):
    k=best_k(s); return exp(-k*s)*Phi(k), exp(-k*s)  # (E/t, a/t)

# --- reviewer cost per FAIR-charging opponent
# field charges lognormal(median mu_f * t, log-sd sf); b = beta*t
def cost(beta, mu_f=0.85, sf=0.35):
    EX = mu_f*exp(sf*sf/2)
    if beta<=0: return 1.5*EX
    z = (log(mu_f)-log(beta))/sf + sf
    return EX + 0.5*EX*Phi(z)

def bq(s, q=1.0/3):   # b = Q_{1/3} of lognormal posterior
    from statistics import NormalDist
    return exp(NormalDist().inv_cdf(q)*s)

for label,s in [("smart sigma=0.2",0.2),("cheap sigma=0.6",0.6)]:
    E,a = income(s); print(f"{label}: a={a:.3f}t  income/opp={E:.4f}t  b=Q13={bq(s):.4f}t  cost/fair-opp={cost(bq(s)):.4f}t")
print(f"default          : a=0     income/opp=0.0000t  b=0        cost/fair-opp={cost(0):.4f}t")
print()

def net_per_item(inc_per_opp, beta, f=0.8, Mm1=19):
    return Mm1*inc_per_opp - Mm1*f*cost(beta)

for f in (0.5,0.8,1.0):
    Eg,_=income(0.2); Ec,_=income(0.6)
    g=net_per_item(Eg,bq(0.2),f); c=net_per_item(Ec,bq(0.6),f); d=net_per_item(0.0,0.0,f)
    swing=g-d; rec=(c-d)/swing
    print(f"f={f}: good={g:+.2f} cheap={c:+.2f} default={d:+.2f} | cheap recovers {rec*100:.1f}% | breakeven uptime {rec*100:.1f}%")

print("\n--- ROBUSTNESS: cheap-recovery fraction (== breakeven uptime) ---")
rows=[]
for mu_f in (0.7,0.85,1.0):
  for sf in (0.25,0.35,0.5):
    for f in (0.5,0.8,1.0):
      for Mm1 in (5,19,39):
        Eg,_=income(0.2); Ec,_=income(0.6)
        bg,bc=bq(0.2),bq(0.6)
        g=Mm1*Eg - Mm1*f*cost(bg,mu_f,sf)
        c=Mm1*Ec - Mm1*f*cost(bc,mu_f,sf)
        d=0      - Mm1*f*cost(0.0,mu_f,sf)
        rows.append((c-d)/(g-d))
print(f"n={len(rows)} scenarios  min={min(rows)*100:.1f}%  median={sorted(rows)[len(rows)//2]*100:.1f}%  max={max(rows)*100:.1f}%")

print("\n--- sigma-flatness of issuer income (why even a blind guess earns) ---")
for s in (0.2,0.4,0.6,0.8,1.0,1.2):
    E,a=income(s); print(f"  sigma={s}: charge a={a:.2f}t -> E[income]={E:.3f}t per opponent")

print("\n--- TOURNAMENT TOTALS (100 games x 8 line items = 800 item-games, units of t) ---")
Eg,_=income(0.2); Ec,_=income(0.6); f=0.8; M=19
g=M*Eg-M*f*cost(bq(0.2)); c=M*Ec-M*f*cost(bq(0.6)); d=-M*f*cost(0.0)
N=800
def T(x): return x*N
print(f"  never submit           : {T(d):>9.0f}")
print(f"  cheap-only, 100% uptime: {T(c):>9.0f}")
for u in (0.70,0.85,0.95):
    print(f"  all-or-nothing smart {u:.0%}: {T(u*g+(1-u)*d):>9.0f}")
for s in (0.70,0.90,1.00):
    print(f"  TWO-PHASE, smart hits {s:.0%}: {T(c+s*(g-c)):>9.0f}")
print()
print(f"  value of 1 rescued game (cheap vs default), 8 items: {8*(c-d):.0f} t")
print(f"  value of 1 upgraded game (smart vs cheap),   8 items: {8*(g-c):.0f} t")
print(f"  cost of a 5h overnight outage (23.8 games)         : {23.8*8*(g-d):.0f} t")
print(f"  total value of sigma 0.6 -> 0.2 across 100 games    : {T(g-c):.0f} t")
print(f"  two-phase@90% MINUS all-or-nothing@85%              : {T(c+0.9*(g-c)) - T(0.85*g+0.15*d):.0f} t")
print(f"  perfect@100% MINUS two-phase@90%                    : {T(g) - T(c+0.9*(g-c)):.0f} t")
