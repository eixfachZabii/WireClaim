# WireClaim — ubiquitous language

Use these words in code, docs, commits and the pitch. Glossary only — mechanics live in
[`README.md`](README.md), decisions in `docs/brainstorm/sebi/adr/`.

## The game

**Game** — one release of one Case, its 60-second submission window, and its Settlement.
There are exactly 100. _Avoid_: round, match, tick

**Case** — the bundle released when a Game opens: a Policy, a Damage Description, an
Invoice, sometimes Images. _Avoid_: claim, packet

**Line Item** — one row of the Invoice, identified by index within its Case. The atomic
unit: every price and threshold is per Line Item. _Avoid_: item, position, Posten

**Settlement** — the scoring of a Game after its window closes, after which its
Transactions become publicly readable. _Avoid_: resolution

## Prices

**Charge** — the gross total we invoice other teams for a Line Item (`a`). Always gross,
always the whole Line Item, never per-unit. _Avoid_: price, bid

**Limit** — the most we will pay when invoiced the same Line Item (`b`). Same gross
convention. _Avoid_: acceptance limit, threshold, b-value

**Fair Value** — the secret per-Line-Item ceiling a claims expert would allow (`t`).
Zero when the Policy does not cover the item. Never observed directly. _Avoid_: true
price, ground truth

**Estimate** — our belief about a Line Item's Fair Value. Always a *distribution*; write
`t̂` only for its median. _Avoid_: prediction, guess

**Cap** — the secret ceiling on what changes hands when a Charge is accepted (`c ≥ 4t`).
_Avoid_: max payout

**Fair Zone / Fraud Zone** — Charges at or below Fair Value / strictly above it. A Charge
in the Fraud Zone is an **Overcharge** — a priced bet, not "fraud". _Avoid_: cheating

## Roles and outcomes

**Issuer** — us in the invoicing role (`H`). _Avoid_: handyman, seller

**Reviewer** — us in the auditing role (`I`). _Avoid_: insurance, adjuster

**Transaction** — one directed Issuer→Reviewer pairing for one Line Item in one Game,
and its outcome. Published after Settlement. _Avoid_: trade, matchup

**Wrongful Rejection** — refusing a Charge that was in the Fair Zone. Costs the Reviewer
`1.5a`; the Issuer still collects `a` and the surplus half is destroyed.

**Wrongful Acceptance** — paying a Charge that was in the Fraud Zone. Our most expensive
mistake, bounded only by the Cap.

**Net** — income as Issuer minus costs as Reviewer. The leaderboard's ranking quantity.
_Avoid_: score, P&L

## Our machine

**Submission** — one (Charge, Limit) pair per Line Item for one Game. Last write wins,
so a Game may receive several. _Avoid_: bid, entry

**Fast Path / Slow Path** — the cheap Submission fired early in the window, and the
considered one that overwrites it. Every Game gets a Fast Path Submission
unconditionally. _Avoid_: fallback, v1/v2

**Price Memory** — the accumulating store of Line Item descriptions paired with Fair
Value brackets recovered from settled Games. _Avoid_: cache, training set

**Field** — the other teams, treated as a population, because one Charge and one Limit
face all of them at once. _Avoid_: opponents, market

**Strategy Track** — one of our competing internal approaches under
`docs/brainstorm/*/strats/`. Never a hackathon track (QuantCo / Viktor / Cognition) —
those are **Challenges**. _Avoid_: track (unqualified), workstream
