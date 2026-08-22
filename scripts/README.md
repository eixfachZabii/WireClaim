# `scripts/`

Two kinds of thing live here, and the distinction matters.

**This directory holds tools** — things you run again, on every Game, forever.
**[`experiments/`](experiments/) holds the measurement record** — one-off harnesses that
produced a number now written into a code comment. Keep them: the methodology is judged, and
a constant whose derivation you cannot re-run is a constant nobody may change.

Everything needs `PYTHONPATH=.`; anything that calls the model also needs
`set -a && . .env && set +a`.

---

## The tools

### Ground truth

| script | what it gives you |
| --- | --- |
| `pull_transactions.py` | every settled Transaction, paginated to the end and cached with a self-check |
| `invert_fair_values.py` | the **exact** Fair Value bracket of every settled Line Item |

The Fair Value is recoverable, not guessable. A rejected Transaction carrying a non-zero
`amount` is a wrongful rejection, so it reveals the issuer's Charge *and* proves `a <= t`; a
rejected Transaction at `0` proves `a > t`. Replaying the payoff table over the result
reproduces every published net to the cent:

```bash
PYTHONPATH=. pixi run python scripts/invert_fair_values.py --games all --verify
```

> Two traps this endpoint sets, both of which have already produced wrong conclusions.
> `/transactions` **paginates at 100 rows**, so page one of a 544-row Game reads exactly like
> a 4-item Case. And `/matrix`'s `cells` array is a **trailing window of the 20 most recently
> completed Games**, not a list indexed by Game id — every cell shifts left as each Game
> settles. Use `matrix()`'s Game-id-keyed mapping, never a positional index.

### Judging a change

| script | what it does |
| --- | --- |
| `replay_payoffs.py` | our net in a real Game had we submitted different numbers, with every opponent held fixed |
| `backtest.py` | scores any Fair Value estimator across every Case |
| `dump_evidence.py` | caches the model's evidence per Case, so re-tuning costs no quota |
| `analyse_game.py` | per-Game post-mortem: attribute every euro to a mechanism |

**Judge in euros, never in log error.** Log error weights a €10 Line Item the same as a
€7,000 one, and the settled distribution runs from single digits to 7,225.

```bash
# what a change is worth, against the real field
PYTHONPATH=. pixi run python scripts/replay_payoffs.py --games all --self-check
# why a Game went the way it did
PYTHONPATH=. pixi run python scripts/analyse_game.py --games 21-30
```

**The noise floor is real.** Two draws of the *identical* prompt differ by **26,622** over
18 Games. Treat any gain under ~30,000 as unproven unless you hold Games out or repeat draws.

### Inputs

| script | what it does |
| --- | --- |
| `build_price_memory.py` | rebuilds `data/price_memory.json` from settled Games |
| `validate_cases.py` | checks Case archives extract and parse |

Re-run `build_price_memory.py` as Games settle — the store is committed because it has to
travel with the code, and it only grows.

---

## Why `experiments/` is kept rather than deleted

Each of those scripts answers one question, in euros, and its answer is already recorded
where the constant lives. Two examples of *negative* results that are worth more than the
code that found them:

- Asking the model for an order-of-magnitude class and letting it pull the price band
  upward: **−127,312** across nineteen Cases.
- Asking for a per-unit rate and multiplying by the invoice quantity: **−64,590**.

Both look obviously sensible. Neither is. If they are not written down, somebody rebuilds
them in three hours' time.
