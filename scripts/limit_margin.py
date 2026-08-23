"""Is our Limit set at the right *level*? Measured at the margin, not on average.

The reviewer's decision is one threshold. Rejecting costs `1.5a` if the Charge was fair and
`0` if it was not; accepting costs `a` either way. So with `q = P(fair)` at the margin:

    accept iff  1.5 * a * q > a      i.e.  q > 2/3

The average rejection is not the decision -- the *marginal* one is. This buckets our own
rejections by how far the opponent's Charge sat above our own Limit (`a / b`) and reports `q`
per bucket, so a level error shows up as the threshold sitting inside a band where `q > 2/3`.

Reconstruction, from the settled cross-section only:
  * `a` -- any row where money moved pays exactly the Charge (accepted, or wrongful rejection).
  * fair -- a rejected row with `amount > 0` proves `a <= t`; `amount == 0` proves `a > t`.
  * `b` -- our own submitted Limit, from `var/decisions/game_NNN.json`.

Censoring cuts the safe way here: a Charge every one of sixteen reviewers rejected at `amount = 0`
is never recoverable, and that is the signature of a *large fraudulent* Charge -- so dropping
those biases `q` UPWARD, and the reported gain is the conservative side of the finding.

See H20 in docs/brainstorm/sebi/strats/review/hypothesis-ledger.md.

    python scripts/limit_margin.py
"""
import json,os,glob
from collections import defaultdict
US='Bin busy'
GAMES=range(82,98)

def game_facts(g):
    charge={}; fair={}
    for p in glob.glob(f'var/transactions/g{g:03d}_*.json'):
        for x in json.load(open(p))['rows']:
            k=(x['line_item_index'],x['issuer']); amt=x['amount']
            if amt>0: charge[k]=amt
            if not x['accepted']:
                fair[k]= (amt>0) if k not in fair else (fair[k] or amt>0)
    return charge,fair

def our_limits(g):
    p=f'var/decisions/game_{g:03d}.json'
    if not os.path.exists(p): return None
    d=json.load(open(p)); items=d.get('items') or d.get('line_items') or d
    if isinstance(items,dict): items=list(items.values())
    out={}
    for i,it in enumerate(items,1):
        if isinstance(it,dict):
            out[it.get('line_item_index',it.get('index',i))]=it.get('limit')
    return out

BK=[(1,1.25,'1.00-1.25x'),(1.25,1.5,'1.25-1.50x'),(1.5,2,'1.50-2.00x'),(2,3,'2.00-3.00x'),(3,1e9,'>3x')]
buckets=defaultdict(lambda:[0,0,0.0])
censored=0; used=0; nolim=0
for g in GAMES:
    lim=our_limits(g)
    if not lim: nolim+=1; continue
    charge,fair=game_facts(g)
    p=f'var/transactions/g{g:03d}_Bin_busy.json'
    if not os.path.exists(p): continue
    for x in json.load(open(p))['rows']:
        if x['reviewer']!=US or x['accepted']: continue
        k=(x['line_item_index'],x['issuer'])
        b=lim.get(x['line_item_index']); a=charge.get(k); f=fair.get(k)
        if b is None or b<=0: continue
        if a is None: censored+=1; continue
        used+=1
        r=a/b
        for lo,hi,name in BK:
            if lo<=r<hi:
                bk=buckets[name]; bk[0]+=1; bk[1]+=int(bool(f)); bk[2]+=a; break

print('OUR REJECTIONS, Games 82-97, bucketed by (opponent charge a) / (our limit b)')
print('accept iff q > 2/3   [reject costs 1.5a if fair, 0 if not; accept costs a]')
print()
print(f"{'a / b':>12}{'n':>6}{'q=P(fair)':>11}{'sum a':>11}{'cost:reject':>13}{'cost:accept':>13}{'gain if accept':>16}")
tot=0.0
for lo,hi,name in BK:
    if name not in buckets: continue
    n,nf,sa=buckets[name]; q=nf/n; avg=sa/n
    rej=1.5*avg*q*n; acc=avg*n; gain=rej-acc
    tot+=gain
    print(f'{name:>12}{n:6d}{q:10.0%}{sa:11,.0f}{rej:13,.0f}{acc:13,.0f}{gain:16,.0f}')
print()
print(f'recoverable rejections used: {used}   unrecoverable (charge never revealed): {censored}')
print('NOTE: unrecoverable = rejected by every reviewer at amount 0 = provably fraudulent,')
print('      so the censoring DROPS fraudulent claims and biases q UPWARD. Treat q as optimistic.')
