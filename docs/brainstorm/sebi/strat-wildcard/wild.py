"""Numerics for docs/strat-wildcard/PLAN.md.  Pure stdlib."""
import math, random, statistics as st

# ───────────────────────────── the rules ─────────────────────────────
def settle(a, b, t, c):
    """Returns (issuer_gets, reviewer_pays)."""
    if a <= t:                       # fair zone
        if a <= b: return a, a
        else:      return a, 1.5 * a
    else:                            # fraud zone
        if a <= b: return min(a, c), min(a, c)
        else:      return 0.0, 0.0

# ─────────────── W1: the aggregate-leaderboard identity ───────────────
MODES = {
    # name             : (charge_factor, limit_factor)  applied to the team's own t_hat
    'correct'          : (0.75, 0.85),
    'net_only'         : (0.75/1.19, 0.85/1.19),   # forgot the 19% VAT
    'double_vat'       : (0.75*1.19, 0.85*1.19),   # grossed up an already-gross rate card
    'per_unit'         : (None, None),             # handled specially: divide by qty
    'per_unit_limit'   : (0.75, None),             # correct charge, per-unit limit
    'flat_limit'       : (0.75, None),             # limit is a constant, ignores t
    'exploiter'        : (None, None),             # charges at its cap guess
    'dark'             : (0.0, 0.0),
}

def make_field(rng, n_teams, mode_w, sigma_est=0.35):
    teams = []
    names = list(mode_w)
    wts   = [mode_w[m] for m in names]
    for i in range(n_teams):
        m = rng.choices(names, weights=wts)[0]
        teams.append({'id': i, 'mode': m, 'bias': math.exp(rng.gauss(0, sigma_est))})
    return teams

def submit(team, t, qty, flat_b=400.0):
    """What this team submits for a Line Item with true Fair Value t and quantity qty."""
    m, th = team['mode'], t * team['bias']
    if m == 'correct':        return 0.75*th, 0.85*th
    if m == 'net_only':       return 0.75*th/1.19, 0.85*th/1.19
    if m == 'double_vat':     return 0.75*th*1.19, 0.85*th*1.19
    if m == 'per_unit':       return 0.75*th/qty, 0.85*th/qty
    if m == 'per_unit_limit': return 0.75*th, 0.85*th/qty
    if m == 'flat_limit':     return 0.75*th, flat_b
    if m == 'exploiter':      return 4.0*th, 0.60*th
    if m == 'dark':           return 0.0, 0.0
    raise KeyError(m)

def play_game(rng, teams, items):
    """items: list of (t, c, qty).  Returns per-team (income, costs) plus ground truth."""
    n = len(teams)
    inc = [0.0]*n; cost = [0.0]*n
    fair_txn = 0; fair_acc = 0; fraud_acc_vol = 0.0; wrongful_vol = 0.0
    fair_charge_sum = [0.0]*n
    for (t, c, qty) in items:
        subs = [submit(tm, t, qty) for tm in teams]
        for i in range(n):
            a = subs[i][0]
            if a <= t and a > 0: fair_charge_sum[i] += a
            for j in range(n):
                if i == j: continue
                g, p = settle(a, subs[j][1], t, c)
                inc[i] += g; cost[j] += p
                if 0 < a <= t:
                    fair_txn += 1
                    if a <= subs[j][1]: fair_acc += 1
                    else:               wrongful_vol += a
                elif a > t and a <= subs[j][1]:
                    fraud_acc_vol += min(a, c)
    return inc, cost, dict(p_true=fair_acc/max(fair_txn,1), wrongful_vol=wrongful_vol,
                           fraud_acc=fraud_acc_vol, fair_charge_sum=fair_charge_sum)

def w1_check(seed=1, n_teams=30, n_items=8, trials=60, mode_w=None):
    rng = random.Random(seed)
    mode_w = mode_w or {'correct':10,'net_only':4,'double_vat':3,'per_unit':2,
                        'per_unit_limit':2,'flat_limit':2,'exploiter':2,'dark':5}
    rows = []
    for _ in range(trials):
        teams = make_field(rng, n_teams, mode_w)
        items = []
        for _ in range(n_items):
            qty = rng.choice([1,1,2,4,8,12,18,25,40])
            t   = math.exp(rng.gauss(math.log(250), 1.0))
            if rng.random() < 0.15: t = 0.0                 # uncovered
            c   = max(4*t, 150.0)
            items.append((t, c, qty))
        inc, cost, gt = play_game(rng, teams, items)
        SI, SC = sum(inc), sum(cost)
        est = 1 - 2*(SC - SI)/SI if SI > 0 else float('nan')
        rows.append((est, gt['p_true'], gt['fraud_acc']/SI if SI>0 else 0,
                     2*(SC-SI), gt['wrongful_vol']))
    err = [r[0]-r[1] for r in rows]
    print("W1  aggregate-leaderboard estimator")
    print(f"    p_hat mean {st.mean(r[0] for r in rows):.3f}   p_true mean {st.mean(r[1] for r in rows):.3f}"
          f"   bias {st.mean(err):+.3f}   sd(err) {st.pstdev(err):.3f}")
    wv = [(r[3], r[4]) for r in rows]
    rel = [abs(x-y)/max(y,1e-9) for x,y in wv]
    print(f"    2*(sum costs - sum income) recovers wrongfully-rejected volume exactly: "
          f"max rel err {max(rel):.2e}")
    print(f"    fraud-accepted share of income {st.mean(r[2] for r in rows):.3f}  (= the optimistic bias)")

# ───────────── W2: what each convention error costs its team ─────────────
def w2_error_cost(seed=3, n_teams=30, n_items=8, trials=200, qty_fixed=None):
    rng = random.Random(seed)
    out = {}
    for victim in ['correct','net_only','double_vat','per_unit','per_unit_limit','dark']:
        tot = 0.0; totinc = 0.0; base_t = 0.0
        r2 = random.Random(seed)
        for _ in range(trials):
            teams = make_field(r2, n_teams-1, {'correct':10,'net_only':4,'double_vat':3,
                                               'per_unit':1,'per_unit_limit':1,'flat_limit':2,
                                               'exploiter':2,'dark':5})
            teams.append({'id':n_teams-1,'mode':victim,'bias':1.0})
            items=[]
            for _ in range(n_items):
                qty = qty_fixed or r2.choice([1,1,2,4,8,12,18,25,40])
                t = math.exp(r2.gauss(math.log(250), 1.0))
                if r2.random() < 0.15: t = 0.0
                items.append((t, max(4*t,150.0), qty)); base_t += t
            inc, cost, _ = play_game(r2, teams, items)
            tot += inc[-1]-cost[-1]; totinc += inc[-1]
        out[victim] = (tot/base_t, totinc/base_t)
    print("\nW2  cost of each convention error (net and income, per unit of true Fair Value)")
    for k,(nt,ic) in out.items():
        print(f"    {k:16s} net/t {nt:+8.3f}   income/t {ic:7.3f}")
    return out

# ───────────── W3: the Cap floor turns small items into cheap options ─────────────
def w3_floor(F_list=(100,200,500,1000), t_list=(10,25,50,100,250,1000)):
    print("\nW3  overcharge break-even p* = t / max(4t, F)   (R5 says 0.25; the floor beats it)")
    hdr = "     t \\ F  " + "".join(f"{F:>9}" for F in F_list); print(hdr)
    for t in t_list:
        row = f"    {t:>6}   " + "".join(f"{t/max(4*t,F):>9.3f}" for F in F_list)
        print(row)

# ───────────── W4: endgame — variance is free when you are behind ─────────────
def w4_endgame(gap_frac=(0.02,0.05,0.10,0.25,0.50), games_left=5, n_opp=29,
               p_accept=0.15, trials=20000, seed=5):
    """Per remaining game we can bank honest income H, or gamble: charge at the Cap on
    every Line Item.  Honest = 1.0*H deterministic.  All-in: each opponent independently
    accepts with prob p, paying 4x the honest charge; misses cost exactly zero (R5)."""
    rng = random.Random(seed)
    print(f"\nW4  endgame gamble, {games_left} games left, p(accept at cap)={p_accept}, {n_opp} opponents")
    print("     gap (x one game's honest income)   P(overtake | honest)   P(overtake | all-in)")
    for gf in gap_frac:
        gap = gf * games_left            # gap measured in games-of-honest-income
        win_h = 1.0 if gap < 1e-12 else 0.0
        wins = 0
        for _ in range(trials):
            tot = 0.0
            for _g in range(games_left):
                acc = sum(1 for _ in range(n_opp) if rng.random() < p_accept)
                tot += 4.0 * acc / n_opp          # in units of one game's honest income
            if tot > gap + games_left: wins += 1  # must beat honest baseline + gap
        print(f"     {gf*games_left:6.2f}                              {win_h:6.3f}                 {wins/trials:6.3f}")

# ───────────── W5: rank-optimal vs net-optimal overcharge bar ─────────────
def w5_rank_bar(c_over_t=(4,6,10), p_fair=(0.3,0.5,0.7,0.9)):
    print("\nW5  overcharge bar: net-optimal p* = t/c ; rank-optimal p* = t(1.25-0.25 p_fair)/c")
    print("     c/t   p_fair   p*_net   p*_rank   ratio")
    for r in c_over_t:
        for pf in p_fair:
            pn = 1.0/r; pr = (1.25-0.25*pf)/r
            print(f"     {r:>3}   {pf:6.2f}   {pn:6.3f}   {pr:7.3f}   {pr/pn:5.2f}")

# ───────────── W6: 50-line baseline vs LLM-quality estimator ─────────────
def w6_baseline(seeds=range(40), n_teams=30, n_items=8):
    """Our net (per unit true Fair Value) for a range of estimator qualities sigma,
    against a mixed Field, playing a=0.75*t_hat, b=0.85*t_hat (the 50-line rule)."""
    print("\nW6  our net per unit of true Fair Value, by estimator log-sd sigma")
    print("     sigma   net/t    income/t   costs/t")
    for sigma in (0.15,0.25,0.35,0.50,0.80,1.20):
        tot=inc_s=cost_s=base=0.0
        for s in seeds:
            rng = random.Random(1000+s)
            teams = make_field(rng, n_teams-1, {'correct':10,'net_only':4,'double_vat':3,
                                                'per_unit':1,'per_unit_limit':1,'flat_limit':2,
                                                'exploiter':2,'dark':5})
            us = {'id':n_teams-1,'mode':'correct','bias':1.0}
            teams.append(us)
            items=[]
            for _ in range(n_items):
                qty = rng.choice([1,1,2,4,8,12,18,25,40])
                t = math.exp(rng.gauss(math.log(250),1.0))
                if rng.random()<0.15: t=0.0
                items.append((t,max(4*t,150.0),qty)); base+=t
            us['bias'] = 1.0
            # give US the sigma-quality estimate by resampling bias per item -> emulate via
            # a per-item wrapper: easiest is to perturb inside play by temporarily setting bias
            inc,cost,_ = play_game_us(rng, teams, items, sigma)
            tot += inc[-1]-cost[-1]; inc_s += inc[-1]; cost_s += cost[-1]
        print(f"     {sigma:5.2f}   {tot/base:+6.3f}   {inc_s/base:7.3f}   {cost_s/base:7.3f}")

def play_game_us(rng, teams, items, sigma_us):
    n=len(teams); inc=[0.0]*n; cost=[0.0]*n
    for (t,c,qty) in items:
        subs=[]
        for k,tm in enumerate(teams):
            if k==n-1:
                th = t*math.exp(rng.gauss(0,sigma_us))
                subs.append((0.75*th, 0.85*th))
            else:
                subs.append(submit(tm,t,qty))
        for i in range(n):
            a=subs[i][0]
            for j in range(n):
                if i==j: continue
                g,p = settle(a,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
    return inc,cost,None

# ───────────── W7: b as a stop-loss — the bound ─────────────
def w7_stoploss(trials=200000, seed=9):
    """Empirically confirm: per-transaction reviewer cost <= max(b, 1.5 t)."""
    rng=random.Random(seed); worst=0.0
    for _ in range(trials):
        t=rng.uniform(0,500); c=max(4*t,150.0); b=rng.uniform(0,1200); a=rng.uniform(0,5000)
        _,pay = settle(a,b,t,c)
        worst=max(worst, pay-max(b,1.5*t))
    print(f"\nW7  max_over_{trials}_draws( reviewer_pay - max(b, 1.5t) ) = {worst:.6f}  (<=0 proves the bound)")

if __name__ == '__main__':
    w1_check()
    w2_error_cost()
    w3_floor()
    w4_endgame()
    w5_rank_bar()
    w6_baseline()
    w7_stoploss()
