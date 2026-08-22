# WireClaim

Our entry to QuantCo's *Claim to Fame* challenge: a tournament in which every team
simultaneously invoices and audits every other team, against a secret notion of a
fair price. This glossary is the ubiquitous language — use these words in code,
docs, commit messages and the pitch. It is a glossary only; mechanics live in
`README.md`, decisions in `docs/adr/`.

## The game

**Game**:
One release of one Case, plus the 60-second window in which every team submits for
it, plus its settlement. There are exactly 100, numbered by the tournament.
_Avoid_: round, match, tick

**Case**:
The bundle released at the start of a Game — a Policy, a Damage Description, an
Invoice, and sometimes Images. Encrypted until its Game opens.
_Avoid_: claim, packet, scenario

**Line Item**:
One row of the Invoice, identified within its Case by index. The atomic unit of
everything: every price, threshold and payoff is per Line Item.
_Avoid_: item, position, row, Posten

**Settlement**:
The tournament's scoring of a Game once its window closes, after which the Game's
Transactions become publicly readable.
_Avoid_: resolution, scoring run

## Prices

**Charge**:
The gross total we invoice other teams for a Line Item. `a` in the rules.
Always gross, always for the whole Line Item, never per-unit, never net.
_Avoid_: price, bid, ask, our price

**Limit**:
The most we will pay when another team invoices us the same Line Item. `b` in the
rules. Same gross-total convention as Charge.
_Avoid_: acceptance limit, threshold, b-value, max price

**Fair Value**:
The secret per-Line-Item price ceiling a claims expert would allow. `t` in the
rules. Zero when the Policy does not cover the item. We never observe it directly.
_Avoid_: true price, ground truth, threshold, t-value

**Estimate**:
Our belief about a Line Item's Fair Value. Always a *distribution*, never a number —
Charge and Limit are different quantiles of it. Write `t̂` only for its median.
_Avoid_: prediction, guess, t-hat (as a scalar)

**Cap**:
The secret per-Line-Item ceiling on what actually changes hands when a Charge is
accepted. `c` in the rules, guaranteed at least four times Fair Value.
_Avoid­_: max payout, ceiling

**Fair Zone / Fraud Zone**:
Charges at or below Fair Value / strictly above it. Naming the zones is fine;
calling a Charge in the Fraud Zone "a fraud" is not — it is an Overcharge, a
deliberate priced bet, and we describe it that way in the write-up.
_Avoid_: cheating, scam

## Roles and outcomes

**Issuer**:
Us in the invoicing role — the handyman. `H` in the rules.
_Avoid_: handyman, customer, seller, claimant

**Reviewer**:
Us in the auditing role — the insurer deciding whether to pay. `I` in the rules.
_Avoid_: insurance, insurer, adjuster, buyer

**Transaction**:
One directed Issuer→Reviewer pairing for one Line Item in one Game, and its
outcome. Published after Settlement.
_Avoid_: trade, matchup, pairing

**Wrongful Rejection**:
A Reviewer refusing a Charge that was in the Fair Zone. Costs the Reviewer 1.5×
the Charge while the Issuer still collects it; the surplus half is destroyed.
_Avoid_: false positive, bad reject

**Wrongful Acceptance**:
A Reviewer paying a Charge that was in the Fraud Zone. Our single most expensive
mistake, bounded only by the Cap.
_Avoid_: false negative, getting scammed

**Net**:
Income as Issuer minus costs as Reviewer, summed over all Transactions. The
leaderboard's ranking quantity and our objective.
_Avoid_: score, P&L, profit

## Our machine

**Submission**:
One (Charge, Limit) pair per Line Item, sent for one Game. Later Submissions
overwrite earlier ones, so a Game may receive several.
_Avoid_: bid, entry, answer

**Fast Path / Slow Path**:
The cheap heuristic Submission fired early in the window, and the considered one
that overwrites it. Every Game gets a Fast Path Submission unconditionally.
_Avoid_: fallback, quick pass, v1/v2

**Price Memory**:
Our accumulating store of Line Item descriptions paired with the Fair Value
brackets recovered from settled Games. The asset that compounds across the 100.
_Avoid_: cache, database, training set

**Field**:
The other teams, treated as a population rather than as individuals — because one
Charge and one Limit face all of them at once.
_Avoid_: opponents, competitors, market

**Strategy Track**:
One of our competing internal approaches, pitched in `docs/strat-*/` and raced
against the others on backtest. Never means a hackathon track (QuantCo / Viktor /
Cognition) — those are Challenges.
_Avoid_: track (unqualified), workstream, lane
