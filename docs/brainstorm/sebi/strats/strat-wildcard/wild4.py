"""Numerics v4: pin the calibration cliff; price the small-item Cap-floor option."""
import math, random, statistics as st
from wild2 import settle, submit, draw_items, MODEW

def bisect_cliff(sig_field, trials=300, lo=0.2, hi=1.2):
    for _ in range(18):
        mid=(lo+hi)/2
        net=play_net(0.70, math.exp(-0.4307*mid), mid, sig_field, trials)
        if net>0: lo=mid
        else:     hi=mid
    return (lo+hi)/2

def play_net(am,bm,sig_us,sig_field,trials=300,n=30,k=8,seed=11,floor_play=None,F=150.0):
    rng=random.Random(seed); tot=0.0; T=0.0
    names=list(MODEW); wts=[MODEW[x] for x in names]
    for _ in range(trials):
        teams=[(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,sig_field)))
               for _ in range(n-1)]
        items=draw_items(rng,k); T+=sum(t for t,_,_ in items)
        inc=[0.0]*n; cost=[0.0]*n
        for (t,c,qty) in items:
            subs=[submit(m,b,t,qty) for (m,b) in teams]
            th=t*math.exp(rng.gauss(0,sig_us))
            a=am*th
            if floor_play is not None and th < F/4.0 and 4*th < F:
                a = F*floor_play                      # take the Cap-floor option instead
            subs.append((a, bm*th))
            for i in range(n):
                aa=subs[i][0]
                for j in range(n):
                    if i==j: continue
                    g,p=settle(aa,subs[j][1],t,c); inc[i]+=g; cost[j]+=p
        tot+=inc[-1]-cost[-1]
    return tot/T

if __name__=='__main__':
    print("A · zero-crossing of our net, as a function of the Field's estimator quality")
    print("    field sigma   our sigma at net=0   ratio")
    for sf in (0.20,0.25,0.35,0.50,0.70):
        x=bisect_cliff(sf)
        print(f"    {sf:11.2f}   {x:18.3f}   {x/sf:5.2f}")

    print("\nB · sensitivity: net vs our sigma at field sigma = 0.35")
    base=None
    for su in (0.20,0.25,0.30,0.35,0.40,0.45,0.50):
        n_=play_net(0.70, math.exp(-0.4307*su), su, 0.35, trials=300)
        if base is None: base=n_
        print(f"    sigma {su:.2f}  net {n_:+6.2f}   ({n_/base*100:5.1f}% of the sigma=0.20 net)")

    print("\nC · the Cap-floor option on small Line Items (absolute floor F = 150)")
    hon=play_net(0.70, math.exp(-0.4307*0.35), 0.35, 0.35, trials=400)
    for fp in (0.5,0.8,1.0):
        alt=play_net(0.70, math.exp(-0.4307*0.35), 0.35, 0.35, trials=400, floor_play=fp)
        print(f"    charge {fp:.1f}*F on items with 4*t_hat < F:  net {alt:+6.2f} "
              f"vs honest {hon:+6.2f}   delta {alt-hon:+6.2f} ({(alt-hon)/abs(hon)*100:+5.1f}%)")
