# Round-trip proven, and two corrections to `Notes.md`

Written Sat 14:06 CEST, ~54 minutes before Game 1.

## The pipeline works

Verified end to end against **game 0**, the permanent test game (`start_time`
2020-01-01, always open, re-submittable as often as we like). We are **`team_id 6`**.

```bash
set -a && . ./.env && set +a                      # TEAM_API_KEY, gitignored

curl -s -H "X-API-Key: $TEAM_API_KEY" \
  https://c2f.public.quantco.cloud/api/games/list                    # 101 games: 0 = test, 1-100 real

KEY=$(curl -s -H "X-API-Key: $TEAM_API_KEY" \
  https://c2f.public.quantco.cloud/api/games/0/key | jq -r .decryption_key)   # 403 before start_time

7z x -y -p"$KEY" -ocase_00 "cases/case_00.zip"     # AES-256; zipfile can't read these

curl -s -X PUT https://c2f.public.quantco.cloud/api/games/0/submissions \
  -H "X-API-Key: $TEAM_API_KEY" -H "Content-Type: application/json" \
  -d '[{"index":1,"charge_price":399.0,"acceptance_limit":420.0}]'
```

`PUT` is **upsert, last-write-wins** — which sanctions the two-phase submit (cheap at
T+3 s, considered overwrite at T+50 s). `422` on negative or non-finite values.
`pypdf` extracts the invoice cleanly; no OCR needed for case 0.

**All 100 encrypted archives are already in the repo.** Only the key drops at T0, so
the hot path is two HTTP calls plus a local decrypt. Nothing needs downloading during
the 60-second window.

## The handbook confirms R7 in the organisers' own words

> "Omitted line items use the game defaults of `charge_price = 0` and
> `acceptance_limit = 0`. **They still participate in transactions; omitting a line
> does not opt the team out of it.**"

Going dark is not scoring zero. It is paying `1.5a` to every opponent on every Line
Item we skip.

## What case 0 teaches about `t`

- **policy.txt** — bicycle theft. Cover requires the bike was locked to a fixed object.
  Indemnity is *"the market value of the bicycle at the time of the theft"*.
- **description.txt** — *"firmly locked against a lamp post"* (⇒ covered) and
  *"the bike was worth 420 Euros"*.
- **invoices.pdf** — one Line Item: `1 | New Bike | 1 | unit`, no price.

So `t = 420`, and it is **stated in the documents**. The starter script's own example
brackets it (`410 / 430`).

**This changes the estimator's centre of gravity.** It is primarily *policy application
and reading comprehension*, not price research: find the indemnity basis in the policy,
find the facts in the description, apply one to the other. The fraud vector here is
**replacement-new vs. market-value** — invoicing a new bike when the policy owes the
depreciated value. Expect the same shape elsewhere: deductibles, sum-insured caps,
"new for old" clauses, exclusion lists. A German trade price table still matters for
the repair cases (the slides show water-damaged laminate with m² quantities), but it is
the second tool, not the first.

## Corrections to `Notes.md`

Three claims in the team notes are right and two are wrong. The wrong ones are
load-bearing.

**✅ "a darf nie über t sein … kosten hier nur opportunity cost bei Ablehnung."**
Correct, and it is the most useful thing in the notes. A rejected Overcharge costs
exactly zero — see README R5.

**✅ "policy violation detection per line item → b = 0."** Correct: on an uncovered item
`t = 0`, so accepting anything is a pure loss.

**❌ "b darf nie unter t sein — das führt zu falscher Ablehnung."**
This is the most expensive belief available in this game. Yes, a wrongful rejection
costs `0.5a` extra — but a wrongful *acceptance* costs `min(a,c)`, and `c ≥ 4t`.
**Being generous is ~8× more expensive than being strict.** The optimal Limit is the
**one-third quantile** of our posterior — the bottom third, deliberately below `t̂`
(README R4, R6). A team that sets `b ≥ t` hands the Cap to every team running the
Overcharge. Worse, since we do not know `t` exactly, "never below `t`" in practice means
"above our estimate", which is exactly the wrong side.

**❌ "(offensichtlich) a = b = t ist optimal."**
Only under certainty. Under uncertainty, charging at the median forfeits the claim half
the time — the optimum is **`a ≈ 0.7 × t̂`**, and `a` and `b` both sit low, near each
other (README R5b, R6). Three independent methods agree. Note this intuition is closer
to right than the "therefore `a > b`" correction I first replaced it with — that was
also wrong, and is recorded as such.

**⚠️ "policy violation → a = t."** If `t = 0` this says charge nothing. But a rejected
Overcharge costs zero, so on uncovered items charging is **weakly dominant** — break-even
is `p > 0`, not 25 % (README R6c). Charge toward the Cap's floor instead of zero. Free
lottery ticket, every Game, including overnight.

**⚠️ "1,5a ≥ b."** This reasoning treats the wrongful-rejection penalty as the bound on
what is worth accepting. It is not: rejecting a *fraudulent* charge costs `0`, not
`1.5a`, so the comparison is between `min(a,c)` and `0` weighted by the probability the
charge is fair. That is what produces the `q > 2/3` rule.

## What to do in the next 50 minutes

1. `pixi install` in `[PUBLIC] EHL Cases/`, or just `pip install requests pypdf` — `7z` is already needed and installed.
2. Get a submitter running that hits **every** Line Item of Game 1 with *something*. Not the good pipeline. Something.
3. Anyone who wants to sanity-check a change: game 0 is always open. Use it.
