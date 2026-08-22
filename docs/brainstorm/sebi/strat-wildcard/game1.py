"""X1 applied to real Game 1 data. Reproduces docs/brainstorm/sebi/strat-wildcard/PLAN.md §0.

Inputs are the four published Net values plus the count of teams at the default.
Nothing else -- no Transactions view, no per-Line-Item data.
"""
N, DARK_NET, N_DARK = 17, -8273.70, 13
SUBS = {'error404 ai': 33436.19, 'Bin busy': 13501.85,
        'Codacabana': 13441.28, 'Non Deterministic': 5683.04}

A_total = -DARK_NET / 1.5                       # a dark team pays 1.5x every Fair Charge
S_net   = N_DARK * DARK_NET + sum(SUBS.values())
W       = -2 * S_net                            # X1:  Sum costs - Sum income = 0.5 W
W_dark  = N_DARK * A_total
W_sub   = W - W_dark
offered = (N - 1) * A_total

print(f"Field Fair-Zone Charge volume (4 Line Items) = {A_total:>12,.2f}")
print(f"Wrongfully Rejected volume W                 = {W:>12,.2f}")
print(f"   dark teams {W_dark:>10,.2f} + awake {W_sub:>10,.2f} = {W_dark + W_sub:>10,.2f}  <- reconciles")
print(f"Fair Charge volume offered                   = {offered:>12,.2f}")
print(f"FIELD ACCEPTANCE RATE p_bar                  = {1 - W / offered:>12.4f}")
print(f"acceptance among the 4 awake teams           = {1 - W_sub / (3 * A_total):>12.4f}")
print(f"break-even Fair Charge total (Net = 0)       = "
      f"[{A_total / 17.0:.2f}, {1.5 * A_total / 17.5:.2f}]  = {A_total / 17.0 / 4:.0f}-{1.5 * A_total / 17.5 / 4:.0f} per Line Item")
print()
for team, net in SUBS.items():                  # net_i = 17 A_i - A_total - 0.5 W_i
    lo = (net + A_total) / 17.0                 # W_i = 0        (accepted everything Fair)
    hi = (net + 1.5 * A_total) / 17.5           # W_i = max      (rejected everything)
    print(f"{team:20s} net {net:>10,.2f}   Fair Charge total in [{lo:8.2f}, {hi:8.2f}]"
          f"   ~{(lo + hi) / 8:6.2f} per Line Item")
