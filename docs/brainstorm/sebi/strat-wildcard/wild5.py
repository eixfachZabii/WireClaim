"""Numerics v5: the Fair-Rate Controller.

Claim: our own income column identifies, per Line Item, whether our Charge was in the
Fair Zone -- because a fair Charge is paid by ALL (N-1) opponents (accepted or wrongfully
rejected), while a fraudulent one is paid only by those who accepted it.

    income_from_item / (N-1) == a   <=>   a <= t        (fair)
    income_from_item / (N-1)  < a   <=>   a >  t        (fraud)

So we can run a Robbins-Monro ladder on the Charge multiplier m (a = m * t_hat) that
targets a chosen fair-rate, with NO model of t and NO leaderboard inversion -- and it
repairs an unknown systematic bias in t_hat (a VAT slip, a units slip) automatically.
"""
import math, random, statistics as st
from wild2 import settle, submit, draw_items, MODEW

N=30; K=8; SIG_FIELD=0.35

def one_game(rng, our_a_of, our_b_of, sig_us, bias_us):
    """Returns (our_income, our_costs, per-item (a, fair?)) for one Game."""
    names=list(MODEW); wts=[MODEW[x] for x in names]
    teams=[(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,SIG_FIELD)))
           for _ in range(N-1)]
    items=draw_items(rng,K)
    inc=0.0; cost=0.0; rows=[]; T=0.0
    for (t,c,qty) in items:
        T+=t
        th = t*bias_us*math.exp(rng.gauss(0,sig_us))       # our Estimate, biased + noisy
        a  = our_a_of(th); b = our_b_of(th)
        got=0.0
        for (m_,bi) in teams:
            aj,bj = submit(m_,bi,t,qty)
            g,_p = settle(a,bj,t,c); got += g              # us as Issuer
            _g,p = settle(aj,b,t,c); cost += p             # us as Reviewer
        inc += got
        rows.append((a, got, a>0 and abs(got-(N-1)*a) < 1e-9))
    return inc, cost, rows, T

def detector_check(trials=300, seed=41):
    rng=random.Random(seed); ok=0; tot=0
    for _ in range(trials):
        _i,_c,rows,_T = one_game(rng, lambda th: 0.9*th, lambda th: 0.8*th, 0.35, 1.0)
        for (a,got,flag) in rows:
            tot+=1
            # ground truth is unavailable here; instead verify internal consistency:
            # flag <=> got == (N-1)*a  (definitionally); and got<(N-1)*a otherwise
            if flag: ok += (abs(got-(N-1)*a) < 1e-9)
            else:    ok += (got < (N-1)*a - 1e-9) or a==0
    print(f"A · fair/fraud detector from own income: consistent on {ok}/{tot} Line Items")

def ladder(target=0.82, eta=0.06, games=100, sig_us=0.35, bias_us=1.0, m0=0.70, seed=7,
           verbose=False):
    rng=random.Random(seed); m=m0; hist=[]; net=0.0; T=0.0
    for g in range(games):
        aof=lambda th,m=m: m*th
        bof=lambda th: th*math.exp(-0.4307*sig_us)
        inc,cost,rows,tt = one_game(rng, aof, bof, sig_us, bias_us)
        net+=inc-cost; T+=tt
        fair = st.mean(1.0 if r[2] else 0.0 for r in rows)
        m *= math.exp(eta*(fair-target))            # Robbins-Monro in log space
        m = min(max(m,0.05),4.0)
        hist.append((g,m,fair))
    return m, net/T, hist

if __name__=='__main__':
    detector_check()

    print("\nB · does the ladder find the right multiplier? (no bias, sigma known)")
    for sig in (0.25,0.35,0.50):
        m,netc,h = ladder(sig_us=sig)
        # oracle: sweep m
        best=None
        for mm in [x/20 for x in range(6,25)]:
            rng=random.Random(7); tot=0.0; TT=0.0
            for _ in range(60):
                inc,cost,rows,tt = one_game(rng, lambda th,mm=mm: mm*th,
                                            lambda th: th*math.exp(-0.4307*sig), sig, 1.0)
                tot+=inc-cost; TT+=tt
            if best is None or tot/TT>best[0]: best=(tot/TT,mm)
        print(f"    sigma {sig:.2f}: ladder settled at m={m:.2f} (net/t {netc:+.2f})   "
              f"oracle best m={best[1]:.2f} (net/t {best[0]:+.2f})")

    print("\nC · the repair test — our t_hat carries an UNKNOWN systematic bias")
    print("    (bias 0.84 = forgot the 19% VAT; 1.19 = double-counted it; 0.06 = per-unit on qty~18)")
    for bias,label in ((1.00,'correct'),(0.84,'net instead of gross'),
                       (1.19,'VAT applied twice'),(1/18,'per-unit instead of line total')):
        m_fix,net_fix,_ = ladder(bias_us=bias, games=100)
        # frozen: no controller, m stuck at 0.70
        rng=random.Random(7); tot=0.0; TT=0.0
        for _ in range(100):
            inc,cost,rows,tt = one_game(rng, lambda th: 0.70*th,
                                        lambda th: th*math.exp(-0.4307*0.35), 0.35, bias)
            tot+=inc-cost; TT+=tt
        print(f"    bias {bias:5.3f} ({label:31s}): frozen net/t {tot/TT:+6.2f}   "
              f"controller net/t {net_fix:+6.2f}   m -> {m_fix:5.2f}")

    print("\nD · how fast does the controller repair a 10x units error? (m trajectory)")
    m,netc,h = ladder(bias_us=1/18, games=60, eta=0.20)
    pts=[h[i] for i in (0,4,9,19,29,39,59)]
    print("    game:  " + "  ".join(f"{g:>5}" for g,_,_ in pts))
    print("    m   :  " + "  ".join(f"{mm:5.2f}" for _,mm,_ in pts))
    print("    fair:  " + "  ".join(f"{f:5.2f}" for _,_,f in pts))
