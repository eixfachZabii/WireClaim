"""Numerics v6: saturation escape, and recovering OUR OWN wrongful-rejection volume."""
import math, random, statistics as st
from wild2 import settle, submit, draw_items, MODEW

N=30; K=8; SIG_FIELD=0.35

def game(rng, m, bmult, sig_us, bias_us):
    names=list(MODEW); wts=[MODEW[x] for x in names]
    teams=[(rng.choices(names,weights=wts)[0], math.exp(rng.gauss(0,SIG_FIELD)))
           for _ in range(N-1)]
    items=draw_items(rng,K)
    inc=0.0; cost=0.0; fairflags=[]; T=0.0
    opp_A=[0.0]*(N-1); opp_inc=[0.0]*(N-1); W_us=0.0; fairvol_in=0.0; F_us=0.0
    subs_cache=[]
    for (t,c,qty) in items:
        T+=t
        th=t*bias_us*math.exp(rng.gauss(0,sig_us)); a=m*th; b=bmult*th
        got=0.0
        for k,(m_,bi) in enumerate(teams):
            aj,bj=submit(m_,bi,t,qty)
            g,_=settle(a,bj,t,c); got+=g
            _g,p=settle(aj,b,t,c); cost+=p
            if 0<aj<=t:
                opp_A[k]+=aj; fairvol_in+=aj
                if aj>b: W_us+=aj
            elif aj>t and aj<=b: F_us+=min(aj,c)
            # opponents' incomes (needed to reconstruct opp_A from public data)
            for l,(m2,bi2) in enumerate(teams):
                pass
        inc+=got
        fairflags.append(abs(got-(N-1)*a)<1e-9)
    return dict(inc=inc,cost=cost,fair=st.mean(1.0 if f else 0.0 for f in fairflags),
                T=T, opp_A=sum(opp_A), W_us=W_us, fairvol_in=fairvol_in, F_us=F_us)

def escape_ladder(bias_us, games=100, eta=0.06, target=0.82, boost=1.6, sig_us=0.35, seed=7):
    rng=random.Random(seed); m=0.70; sat=0; net=0.0; T=0.0; traj=[]
    for g in range(games):
        r=game(rng,m,math.exp(-0.4307*sig_us),sig_us,bias_us)
        net+=r['inc']-r['cost']; T+=r['T']
        if r['fair']>0.999:
            sat+=1
            m *= boost if sat>=2 else math.exp(eta*(r['fair']-target))
        else:
            sat=0; m*=math.exp(eta*(r['fair']-target))
        m=min(max(m,0.02),60.0); traj.append((g,m,r['fair']))
    return m, net/T, traj

if __name__=='__main__':
    print("A · saturation escape: two consecutive 100%-fair Games => multiply m by 1.6")
    for bias,label in ((1/18,'per-unit (qty~18)'),(1/6,'per-unit (qty~6)'),(0.84,'net not gross'),(1.0,'correct')):
        m,net,traj=escape_ladder(bias)
        pts=[traj[i] for i in (0,2,4,6,9,14,29,99)]
        print(f"    bias {bias:6.3f} ({label:20s}) -> m={m:6.2f}, net/t {net:+6.2f}")
        print("        game " + " ".join(f"{g:>6}" for g,_,_ in pts))
        print("        m    " + " ".join(f"{mm:6.2f}" for _,mm,_ in pts))

    print("\nB · recovering our OWN wrongful-rejection volume from public aggregates")
    print("    W_us = 2*(our costs - sum_j A_j) - 2*F_us ;  A_j = income_j/(N-1)")
    rng=random.Random(3)
    for bmult,label in ((math.exp(-0.4307*0.35),'b = Q13 (correct)'),
                        (0.06,'b = per-unit bug'),(2.5,'b = generous')):
        rows=[]
        for _ in range(40):
            r=game(rng,0.70,bmult,0.35,1.0)
            est_W = 2*(r['cost']-r['opp_A'])           # ignores F_us
            rows.append((est_W, r['W_us'], r['F_us'], r['fairvol_in']))
        relerr=[abs(e-w)/max(w,1e-9) for e,w,_,_ in rows if w>0]
        share=[w/f for _,w,_,f in rows if f>0]
        print(f"    {label:20s}: recovered W_us rel err (median) {st.median(relerr) if relerr else 0:.4f}"
              f"   | wrongfully-rejected share of incoming fair volume = {st.mean(share):.3f}")
