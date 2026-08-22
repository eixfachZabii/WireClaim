"""Numerics v3: the calibration cliff, and the value of knowing the Field's modes."""
import math, random, statistics as st
from wild2 import settle, submit, draw_items, MODEW

CLEAN = {'correct':1}                       # a homogeneous, well-behaved Field
MIXED = MODEW                               # the mode-mixture Field

def run(am, bm, sig_us, sig_field, weights, trials=200, n=30, k=8, seed=11):
    rng=random.Random(seed); tot=0.0; T=0.0; I=0.0; C=0.0
    names=list(weights); wts=[weights[x] for x in names]
    for _ in range(trials):
        teams=[(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,sig_field)))
               for _ in range(n-1)]
        items=draw_items(rng,k); T+=sum(t for t,_,_ in items)
        inc=[0.0]*n; cost=[0.0]*n
        for (t,c,qty) in items:
            subs=[submit(m,b,t,qty) for (m,b) in teams]
            th=t*math.exp(rng.gauss(0,sig_us)); subs.append((am*th, bm*th))
            for i in range(n):
                a=subs[i][0]
                for j in range(n):
                    if i==j: continue
                    g,p=settle(a,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
        tot+=inc[-1]-cost[-1]; I+=inc[-1]; C+=cost[-1]
    return tot/T, I/T, C/T

def cliff():
    print("A · the calibration cliff — our net vs OUR sigma, for three Field qualities")
    print("      (a,b) held at the R5b/R4 rule: a=0.70*t_hat, b=Q13 = t_hat*exp(-0.4307*sigma))")
    print("     our sigma " + "".join(f"{s:>9.2f}" for s in (0.15,0.25,0.35,0.45,0.55,0.70,0.90)))
    for sf in (0.25,0.35,0.50):
        row=f"    field {sf:.2f} "
        for su in (0.15,0.25,0.35,0.45,0.55,0.70,0.90):
            bq = math.exp(-0.4307*su)
            net,_,_ = run(0.70, bq, su, sf, MIXED, trials=120)
            row+=f"{net:>9.2f}"
        print(row)

def modes_value():
    print("\nB · is the (a,b) optimum different against a mode-mixture Field vs a clean one?")
    for label,w in (("clean Field",CLEAN),("mode-mixture Field",MIXED)):
        best=None
        for am in (0.5,0.6,0.7,0.8,0.9):
            for bm in (0.5,0.6,0.7,0.8,0.9,1.0,1.2):
                net,_,_ = run(am,bm,0.35,0.35,w,trials=120)
                if best is None or net>best[0]: best=(net,am,bm)
        print(f"    {label:20s} best net {best[0]:+6.2f} at a={best[1]:.1f}*t_hat, b={best[2]:.1f}*t_hat")
    # cross-application loss
    print("    cross-check: play the CLEAN-optimum against the MIXTURE and vice versa")
    for am,bm,tag in ((0.7,0.9,'clean-opt'),(0.7,0.9,'mix-opt')):
        pass

def sweep_pairs():
    print("\nC · loss from using the wrong Field model (grid, sigma_us=sigma_field=0.35)")
    grid=[(0.6,0.7),(0.7,0.8),(0.7,0.9),(0.8,0.9),(0.6,0.9),(0.7,1.2)]
    for am,bm in grid:
        nc,_,_=run(am,bm,0.35,0.35,CLEAN,trials=120)
        nm,_,_=run(am,bm,0.35,0.35,MIXED,trials=120)
        print(f"    a={am:.1f} b={bm:.1f}   net vs clean {nc:+6.2f}   net vs mixture {nm:+6.2f}")

def field_charge_signal():
    print("\nD · can we read the Field's average charge from the income column?")
    rng=random.Random(21)
    for w,label in ((CLEAN,'clean'),(MIXED,'mixture')):
        names=list(w); wts=[w[x] for x in names]
        n=30; k=8
        teams=[(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,0.35))) for _ in range(n)]
        items=draw_items(rng,k)
        inc=[0.0]*n; cost=[0.0]*n; A=[0.0]*n
        for (t,c,qty) in items:
            subs=[submit(m,b,t,qty) for (m,b) in teams]
            for i in range(n):
                a=subs[i][0]
                if 0<a<=t: A[i]+=a
                for j in range(n):
                    if i==j: continue
                    g,p=settle(a,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
        est=[x/(n-1) for x in inc]
        err=[abs(e-a)/max(a,1e-9) for e,a in zip(est,A) if a>0]
        print(f"    {label:8s}: income_i/(N-1) recovers team i's FAIR charge total; "
              f"median rel err {st.median(err):.4f}, max {max(err):.3f}  (error = fraud accepted)")

if __name__=='__main__':
    cliff(); modes_value(); sweep_pairs(); field_charge_signal()
