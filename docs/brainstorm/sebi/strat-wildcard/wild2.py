"""Numerics v2 for docs/strat-wildcard/PLAN.md.  Pure stdlib."""
import math, random, statistics as st

def settle(a, b, t, c):
    if a <= t:  return (a, a) if a <= b else (a, 1.5*a)
    else:       return (min(a,c), min(a,c)) if a <= b else (0.0, 0.0)

MODEW = {'correct':10,'net_only':4,'double_vat':3,'per_unit':1,'per_unit_limit':1,
         'flat_limit':2,'exploiter':2,'dark':5}

def submit(mode, bias, t, qty, flat_b=400.0, ac=0.75, bc=0.85):
    th = t*bias
    if mode=='correct':        return ac*th, bc*th
    if mode=='net_only':       return ac*th/1.19, bc*th/1.19
    if mode=='double_vat':     return ac*th*1.19, bc*th*1.19
    if mode=='per_unit':       return ac*th/qty, bc*th/qty
    if mode=='per_unit_limit': return ac*th, bc*th/qty
    if mode=='flat_limit':     return ac*th, flat_b
    if mode=='exploiter':      return 4.0*th, 0.60*th
    if mode=='generous':       return ac*th, 2.5*th
    if mode=='dark':           return 0.0, 0.0
    raise KeyError(mode)

def draw_field(rng, n, sigma=0.35, weights=None):
    w = weights or MODEW; names=list(w); wts=[w[k] for k in names]
    return [(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,sigma))) for _ in range(n)]

def draw_items(rng, k, pi0=0.15):
    out=[]
    for _ in range(k):
        qty = rng.choice([1,1,2,4,8,12,18,25,40])
        t = 0.0 if rng.random()<pi0 else math.exp(rng.gauss(math.log(250),1.0))
        out.append((t, max(4*t,150.0), qty))
    return out

def play(teams, items):
    """teams: list of (mode,bias). Returns income[], costs[], diagnostics."""
    n=len(teams); inc=[0.0]*n; cost=[0.0]*n
    A=[0.0]*n          # each team's FAIR charge total
    W=[0.0]*n          # each team's wrongfully-rejected-BY-them volume
    F=0.0; fair_vol=0.0; rej_vol=0.0
    for (t,c,qty) in items:
        subs=[submit(m,b,t,qty) for (m,b) in teams]
        for i in range(n):
            a=subs[i][0]
            if 0 < a <= t: A[i]+=a
            for j in range(n):
                if i==j: continue
                g,p=settle(a,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
                if 0 < a <= t:
                    fair_vol += a
                    if a > subs[j][1]: W[j]+=a; rej_vol+=a
                elif a>t and a<=subs[j][1]: F += min(a,c)
    p_vol = 1 - rej_vol/fair_vol if fair_vol>0 else float('nan')
    return inc,cost,dict(A=A,W=W,F=F,p_vol=p_vol,fair_vol=fair_vol,rej_vol=rej_vol)

# ══════════════════ W1 · aggregate-leaderboard identity ══════════════════
def w1(trials=200, n=30, k=8, seed=1):
    rng=random.Random(seed); errs=[]; fshare=[]; idn=[]; idn2=[]
    for _ in range(trials):
        teams=draw_field(rng,n); items=draw_items(rng,k)
        inc,cost,d=play(teams,items)
        SI,SC=sum(inc),sum(cost)
        idn.append(abs(2*(SC-SI)-sum(d['W']))/max(sum(d['W']),1e-9))
        phat = 1-2*(SC-SI)/SI
        errs.append(phat-d['p_vol']); fshare.append(d['F']/SI)
        # per-team identity  net_i = (n-1)*A_i - sum_{j!=i} A_j - 0.5 W_i  (+ fraud terms)
        i=0
        lhs=inc[i]-cost[i]
        rhs=(n-1)*d['A'][i]-(sum(d['A'])-d['A'][i])-0.5*d['W'][i]
        idn2.append(lhs-rhs)
    print("W1  aggregate identity")
    print(f"    2*(Sum costs - Sum income) == wrongfully-rejected volume : max rel err {max(idn):.2e}")
    print(f"    p_hat = 1 - 2(SC-SI)/SI  vs volume-weighted truth: bias {st.mean(errs):+.4f}  sd {st.pstdev(errs):.4f}")
    print(f"    fraud-accepted share of income {st.mean(fshare):.4f}  (this IS the bias, one-for-one)")
    print(f"    per-team net identity residual (nonzero only via fraud transfers): "
          f"mean {st.mean(idn2):+.2f}, share of |net| {abs(st.mean(idn2))/1000:.3f}")

# ══════════════════ W2 · what each convention error costs ══════════════════
def w2(trials=400, n=30, k=8, seed=3, sigma=0.35):
    print("\nW2  cost of each convention error (per unit of the victim's own true Fair Value)")
    print("    mode              income/t   costs/t    net/t    dNet vs correct")
    base={}
    for victim in ['correct','generous','net_only','double_vat','per_unit',
                   'per_unit_limit','flat_limit','dark']:
        rng=random.Random(seed); I=C=0.0; T=0.0
        for _ in range(trials):
            teams=draw_field(rng,n-1,sigma)
            teams.append((victim, math.exp(rng.gauss(0,sigma))))
            items=draw_items(rng,k)
            T+=sum(t for t,_,_ in items)
            inc,cost,_=play(teams,items); I+=inc[-1]; C+=cost[-1]
        base[victim]=(I/T,C/T,(I-C)/T)
    ref=base['correct'][2]
    for m,(i_,c_,n_) in base.items():
        print(f"    {m:16s} {i_:8.2f}  {c_:8.2f}  {n_:+8.2f}   {n_-ref:+8.2f}")
    return base

# ══════════════════ W3 · Cap floor  ══════════════════
def w3():
    print("\nW3  overcharge break-even p* = t / max(4t, F)")
    Fs=(100,200,500,1000)
    print("      t \\ F " + "".join(f"{F:>9}" for F in Fs))
    for t in (10,25,50,100,250,1000):
        print(f"    {t:>7}  " + "".join(f"{t/max(4*t,F):>9.3f}" for F in Fs))

# ══════════════════ W4 · endgame gamble, independent vs common-factor ══════════════════
def w4(games=5, n_opp=29, trials=40000, seed=5):
    print("\nW4  endgame all-in (charge at Cap=4t on everything) vs banking honest income")
    print("    units: one game's honest income = 1.0   |   all-in mean = 4*E[p]")
    for label, common in (("independent b (naive)",False),("common-factor b (real)",True)):
        for p in (0.10,0.20,0.30):
            rng=random.Random(seed); tot=[]
            for _ in range(trials):
                s=0.0
                for _g in range(games):
                    if common:
                        # one shared generosity draw per game -> acceptance is near all-or-nothing
                        u=rng.random()
                        frac = 1.0 if u < p else 0.0
                        frac = 0.9*frac + 0.1*sum(1 for _ in range(n_opp) if rng.random()<p)/n_opp
                    else:
                        frac = sum(1 for _ in range(n_opp) if rng.random()<p)/n_opp
                    s += 4.0*frac
                tot.append(s)
            m=st.mean(tot); sd=st.pstdev(tot)
            beat = sum(1 for x in tot if x>games)/trials
            print(f"    {label:24s} p={p:.2f}  mean {m:5.2f}  sd {sd:5.2f}  "
                  f"P(all-in beats honest over {games} games) = {beat:5.3f}")

# ══════════════════ W5 · rank vs net bar ══════════════════
def w5():
    print("\nW5  overcharge bar: net-optimal p* = t/c ;  rank-optimal p* = t(1.25-0.25*p_fair)/c")
    for r in (4,6,10):
        row=f"    c/t={r:>2}: "
        for pf in (0.3,0.5,0.7,0.9):
            row+=f" p_fair={pf:.1f}: {1.0/r:.3f}->{(1.25-0.25*pf)/r:.3f} "
        print(row)

# ══════════════════ W6 · the 50-line baseline: (a,b) multiplier sweep ══════════════════
def w6(trials=120, n=30, k=8, seed=7):
    print("\nW6  our net per unit of true Fair Value, sweeping the two multipliers")
    for sig in (0.25,0.45,0.65):
        print(f"    -- our estimator log-sd sigma = {sig} --")
        print("       b\\a " + "".join(f"{a:>8.2f}" for a in (0.5,0.6,0.7,0.8,0.9,1.0)))
        for bm in (0.0,0.3,0.5,0.7,0.9,1.2,2.0):
            row=f"    {bm:6.2f} "
            for am in (0.5,0.6,0.7,0.8,0.9,1.0):
                rng=random.Random(seed); tot=0.0; T=0.0
                for _ in range(trials):
                    teams=draw_field(rng,n-1); items=draw_items(rng,k)
                    T+=sum(t for t,_,_ in items)
                    inc=[0.0]*n; cost=[0.0]*n
                    for (t,c,qty) in items:
                        subs=[submit(m,b,t,qty) for (m,b) in teams]
                        th=t*math.exp(rng.gauss(0,sig))
                        subs.append((am*th, bm*th))
                        for i in range(n):
                            a=subs[i][0]
                            for j in range(n):
                                if i==j: continue
                                g,p=settle(a,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
                    tot += inc[-1]-cost[-1]
                row+=f"{tot/T:>8.2f}"
            print(row)

# ══════════════════ W7 · stop-loss bound ══════════════════
def w7(trials=300000, seed=9):
    rng=random.Random(seed); worst=-1e9
    for _ in range(trials):
        t=rng.uniform(0,500); c=max(4*t,150.0); b=rng.uniform(0,1200); a=rng.uniform(0,5000)
        worst=max(worst, settle(a,b,t,c)[1]-max(b,1.5*t))
    print(f"\nW7  max(reviewer pay - max(b,1.5t)) over {trials} random draws = {worst:.6f}  (<=0 proves it)")

if __name__=='__main__':
    w1(); w2(); w3(); w4(); w5(); w6(); w7()
