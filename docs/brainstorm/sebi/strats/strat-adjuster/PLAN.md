# Strategy: **The Adjuster**

> Build the real thing — a genuine agentic claims adjuster with hard domain grounding.
>
> Competing pitch for `docs/STRATEGY-INDEX.md`. Assumes `README.md` (R1–R9) as read
> and proven; this document does not re-derive the game theory, it *sharpens two of
> the results* (§2.3) and builds the estimator that R1–R9 all depend on.

---

## 0. What we already know that nobody else has bothered to look at

Before the bet: three facts extracted from QuantCo's own slide 5, which shows the
real `invoices.pdf` at full resolution. This is the entire input contract and it
changes the design.

```
INVOICE NO.  2026-0028   DATE 07 Aug 2026   DUE DATE 14 Aug 2026   TRADE  Flooring

FROM  StolperFrei Bodenverlegung GmbH        TO  European Hackathon
      Laminatweg 19                              Hauptstraße 1
      3800 Klicksburg                            8000 Munich

LINE ITEMS
POS.  DESCRIPTION                                             QTY  UNIT  UNIT PRICE  VAT  TOTAL
1     Remove water-damaged laminate in living room             18   m²      ____     ___  _____
2     New installation of laminate incl. impact sound insul.   18   m²      ____     ___  _____
3     Replace skirting boards                                  25   lm      ____     ___  _____

Net           ______
plus VAT      ______
Total amount  ______
```

**F1 — The invoice carries an explicit `TRADE` field.** "Flooring". That is a free,
zero-latency routing key into a trade-specific rate card *before we read a single
line item*. Every competitor will throw the whole PDF at a model and hope. We
dispatch on a field the generator handed us.

**F2 — `QTY` and `UNIT` are printed. We never have to infer them.** `18 / m²`,
`25 / lm`. This is enormous: the hardest half of pricing (how much of it?) is given.
The task collapses to *unit price × a quantity we already have*, which is exactly
the shape of a lookup table. It also means the invoice-level free parameter the
generator controls is the **unit price**, and `t = qty × fair_unit_price`.

**F3 — The `Net / plus VAT / Total amount` footer confirms the gross convention and
tells us the generator computes net first.** Our submission is `Total` = the gross
line total. So every number in our knowledge base should be stored **net**, and
grossed up by ×1.19 at the last step, exactly as the generator almost certainly does.
Two teams will lose the entire tournament to a missing ×1.19 — a 16% systematic
undercharge and, worse, a `b` that wrongfully rejects every fair claim near `t`.

**F4 — Line-item text is English; the domain is German.** "Remove water-damaged
laminate", not "Entfernung wassergeschädigtes Laminat". German only leaks through in
the flavour: `StolperFrei Bodenverlegung GmbH`, `Laminatweg 19`, `Hauptstraße 1`,
`8000 Munich`, `m²`, `lm`. So: no umlaut hell in the item text (but `ß`, `²`, `€`
still appear elsewhere — encoding still has to be right), and our knowledge base
must be keyed on **English canonical concepts backed by German trade economics**.

**F5 — The optional photo is a stock image, and it does not match the invoice.**
Slide 5's photo shows a *kitchen* sink leak with a rotted cabinet base and a stained
wall; the invoice is for a *living-room* floor. Whether that is slide sloppiness or a
property of the generator, the conclusion is the same and it is load-bearing for §6:
**images are a categorical relatedness signal, never a measurement.** No photograph
tells you 18 m² versus 30 m². Budget latency accordingly.

---

## 1. The bet in one paragraph

Every other team will paste `policy.txt`, `description.txt` and the PDF text into one
LLM call and ask "what is a fair price for these line items?". That produces an
estimate with a log-scale spread of roughly ±2–5×, because a language model asked a
naked pricing question has no anchor and hedges wide. Our bet is that **`t` is not a
vibe — it is a *constructed* quantity**, and it is constructed the way a German
claims expert constructs it: three independent gates (is it **covered**, is it
**related**, is the price **reasonable**), and the third gate is not an opinion but an
arithmetic build-up, `t = quantity × (material + Stundensatz × Zeitansatz)`, grossed
up by 19% VAT. We therefore ship a **seeded German trade price knowledge base** —
real €/m², €/lfm and €/h anchors with sources — and a three-agent adjudication
pipeline that produces a *calibrated posterior* on `t` rather than a number. §2.3
shows the payoff exactly: the expected income the README's own R5b objective yields
is a function of posterior width alone, and tightening σ<sub>log</sub> from 0.5
(vibes) to 0.25 (grounded) raises captured fair-value income from **47.5% to 63.6%**
— a **+34% income lift on every line item of every one of the 100 games**, available
from game 1 with zero labels, before R9's leaderboard learning has produced a single
data point.

---

## 2. Why this wins

### 2.1 It is the only lever that is linear in effort and compounds from game 1

Read the README's priority list. #1 (never miss a game) and #2 (submit twice) are
*uptime* — hard requirements, but they are a fixed cost: one engineer, four hours,
done, and every serious team will have them. #4 (compound over 100 rounds via R9)
only starts paying after enough games have settled to invert. #3 — *estimate `t`
well* — is the only item on the list that (a) pays from game 1, (b) has no ceiling,
and (c) is where a 21-hour team can actually out-engineer the field, because it is
the only place where **domain knowledge substitutes for data we do not have**.

R9 gives us labels, but the first settled game is at ~15:01 Saturday and a usable
per-item posterior needs tens of games. The knowledge base is what carries games
1–20, and it is what R9's Bayesian update *shrinks toward* thereafter. A team with no
prior has nothing to shrink toward and spends its first twenty games as a random
number generator — and R7 has already established that being wrong is not neutral, it
bleeds.

### 2.2 The three gates are three *different* questions, and conflating them is the field's mistake

The handout is unusually explicit: a claim fails if it *isn't insured*, *is unrelated
to the case*, or *is inflated*. Those are not three flavours of one judgement, they
are three predicates with three different evidence sets:

| Gate | Reads | Answers | Failure mode if merged into one prompt |
| --- | --- | --- | --- |
| **Coverage** | `policy.txt` + item text | Is `t = 0`? | The model prices a plausible item without ever opening the policy |
| **Relatedness** | `description.txt` + `images.png` + item text | Is `t = 0`? Is `qty` inflated? | The model accepts any item the trade could plausibly do |
| **Price** | item text + `qty` + `unit` + KB | What is `t` given it survives? | The model's number is unanchored and its spread is enormous |

A single prompt that asks all three at once gets all three badly, because the model's
attention is spent on the *price* question — the one that looks like the task — and
coverage is answered as an afterthought. Splitting them means each agent sees a small
context, answers one question, and **cites its evidence** (the policy clause, the
description sentence, the build-up arithmetic). Which is also, not coincidentally,
what makes the write-up write itself.

### 2.3 The mathematics: posterior width, not posterior centre, is the money

This is the sharp version of the argument, derived from the README's own R5b, and it
is worth stating precisely because it also **corrects R5b in a direction that helps
us**.

R5b's issuer objective with `p(a) = 0` (the overnight regime, ~48 games) is
`E[income] = a · G(a)` where `G(a) = P(t ≥ a)`. Model the posterior on `t` as
log-normal with median `m` and log-scale `σ`. Then `a·G(a)` is maximised where

```
1 − Φ(z*) = φ(z*) / σ ,      a* = m · exp(z*·σ)
```

Solving numerically, and normalising expected income by `E[t] = m·exp(σ²/2)` — which
is exactly the income a perfectly-informed team would collect by charging `a = t`
every time — gives:

| σ<sub>log</sub> | 90% CI on `t` | `a*` / median | `P(a* ≤ t)` | **share of attainable income captured** |
| --- | --- | --- | --- | --- |
| 0.15 | ×[0.78, 1.28] | 0.80 | 92.6% | **73.7%** |
| **0.25** | ×[0.66, 1.51] | 0.76 | 86.7% | **63.6%** |
| 0.50 | ×[0.44, 2.28] | 0.77 | 70.2% | **47.5%** |
| 0.80 | ×[0.27, 3.73] | 1.00 | 50.0% | **36.3%** |
| 1.00 | ×[0.19, 5.18] | 1.36 | 38.0% | **31.3%** |
| 1.50 | ×[0.09, 11.9] | 4.32 | 16.5% | **23.1%** |

Three things fall out, all of them useful:

1. **Income is roughly linear in log-precision.** Halving `σ` from 0.50 to 0.25 buys
   +34% income. Nothing else in this tournament is a 34% lever available before the
   first game. This *is* the strategy.
2. **R5b's "the optimum sits at or above the median" is the σ > 0.8 regime.** The
   crossover is at exactly `σ = 0.8` (where `1−Φ(0) = 0.5 = φ(0)/0.8`). Above it, the
   log-normal tail is so fat that charging above your median is right. Below it, the
   revenue-maximising honest charge is around **0.76 × median** and is remarkably
   stable there for all σ ∈ [0.2, 0.6]. In other words: *R5b as written is correct
   advice for a team that is guessing, and wrong advice for a team that knows.* The
   whole point of this plan is to move us out of the regime where R5b's stated
   corollary applies. **Do not charge above the median once the KB is live.**
3. **Therefore, overnight, `a < b`, and R6 is a daytime result.** With `p ≈ 0` the
   issuer wants `Q₀.₁₃` and the reviewer wants `Q₁ᐟ₃` (R4), so the correct submission
   is `a = 0.76m < b = 0.90m`. R6's "aggressive as issuer, timid as reviewer" is a
   statement about the *free-option* regime (Saturday afternoon, `p` large), where
   R5's logic drives `a` out toward the cap and `a ≫ b`. Both are right; the switch
   is `p`, and `p` is measured. Anyone who hard-codes `a > b` will be systematically
   overcharging through the entire night and collecting nothing.

### 2.4 The uncovered-item play: a corollary nobody else will find

Combine the Coverage gate with R5. If an item is **not covered**, then `t = 0`, so
*every* charge is in the fraud zone, so — by R5 — the charge costs us **exactly
nothing** if rejected, and the forgone honest income is `t = 0`. An uncovered line
item is therefore a **pure free option with zero premium**.

The optimal `a` on an uncovered item is not "the highest number we dare". It is
**precisely the number a competent-but-ungated team would believe is fair**, because
that maximises `p(a)`, the share of opponents whose `b` sits above it. Every team that
skipped the coverage check will have set `b ≈ Q₁ᐟ₃(their price posterior)` on that
item; landing just under the mode of that distribution converts their oversight into
our income at zero risk.

So on an uncovered item: **`a` = our best *ungated* fair-price estimate; `b` = 0.**
That is a genuinely asymmetric play, and it is only available to a team that runs
coverage as a separate gate. It is also the single most QuantCo-flavoured moment in
the whole strategy, and the one slide that will make them sit up.

### 2.5 The style argument: this *is* QuantCo's product

Slide 2 of their own deck is a three-box architecture:

```
   Intake  ─▶  Claims Agents & Statistical Modelling  ─▶  Human In the Loop Workplace
```

Slide 3 names the steps of claim assessment: *plausibility & coverage check*, *fraud
& recourse detection*, *cost estimation*, *check invoices*. The public record on
QuantCo's insurance line describes in-house OCR for document digitalisation, fraud
detection, and **motor-vehicle damage residual estimation** — the German P&C claims
stack, sold to large European insurers.

Our architecture is a one-to-one map onto their slide:

| QuantCo slide | WireClaim component |
| --- | --- |
| **Intake** — "more and better data" | §5 Extractor: deterministic PDF→structured line items, unit normalisation, fallback OCR |
| **Claims Agents** — plausibility & coverage check, fraud detection, cost estimation | §3 Coverage / Relatedness / Price agents |
| **Statistical Modelling** — better decisions | §3.5 log-normal posterior, R9 Bayesian shrinkage, R4's `Q₁ᐟ₃` decision rule |
| **Human In the Loop** — "speed up humans & feedback for AI" | §5 ops dashboard: every `a`/`b` carries its citations, its build-up, and an override slider; R9 settlements feed back as labels |
| **Enablement & Integration Layer** | the runner, the KB as a versioned artefact, the calibration loop |

Two teams will win the leaderboard by luck. One team will hand QuantCo a working
miniature of the product they sell, with a calibration plot. When the write-up says
*"we built the Claims Assessment box from your slide 2, here is the coverage gate
citing §4.2 of the policy, here is the price build-up at 48 €/h Bodenleger-Stundensatz,
here is our empirical coverage against the R9-recovered `t` brackets"* — that is not a
hackathon hack, that is a demo of their roadmap. **Style is not a tiebreak here, it is
a second prize, and this is the only design that competes for it.**

---

## 3. The adjudication pipeline

### 3.0 Shape

```
                     ┌─────────────── FAST PATH (T+0 → T+6s) ────────────────┐
  key ─▶ 7z ─▶ EXTRACT ─▶ CANONICALISE ─▶ KB lookup ─▶ (a,b) ─▶ SUBMIT #1
                  │           │                                  guaranteed
                  │           └────────────┬──────────────┐      floor
                  │                        │              │
                  ▼                        ▼              ▼
            ┌───────────┐          ┌──────────────┐  ┌──────────┐
            │ COVERAGE  │          │ RELATEDNESS  │  │  PRICE   │   SLOW PATH
            │  agent    │          │    agent     │  │  agent   │   (parallel,
            │ policy.txt│          │description   │  │ KB + qty │    T+2 → T+20s)
            │  + items  │          │+ images.png  │  │ + trade  │
            └─────┬─────┘          └──────┬───────┘  └────┬─────┘
                  │ π_cov, clause         │ π_rel, κ_qty  │ (lo,mid,hi), σ
                  └────────────┬──────────┴───────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  POSTERIOR ASSEMBLY  │  mixture: π₀ at 0, LogN(μ,σ) else
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐   p(a) from R9 leaderboard
                    │  DECISION (R4/R5b)   │◀── aggression controller
                    └──────────┬───────────┘
                               ▼
                     SUBMIT #2  (T+25s typical, hard cut T+48s)
```

Everything after `SUBMIT #1` is **optional refinement**. That is the whole answer to
"this pipeline is too elaborate for 60 seconds": the elaborate part cannot cause a
missed game, because a submission is already on file before it starts.

### 3.1 Extractor (deterministic, no model)

Owns the one thing that must never fail.

```python
@dataclass(frozen=True)
class LineItem:
    index: int            # 0-based; the submission array index
    pos: str              # "1", "2.1", "3a" as printed
    description: str      # verbatim
    qty: float | None
    unit: Unit | None     # SQM | LM | EACH | HOUR | DAY | KG | M3 | FLAT | AW
    page: int
    raw_row: str          # for debugging + prompt context

@dataclass(frozen=True)
class Case:
    game_id: str
    trade: str | None     # "Flooring" — from the TRADE header field
    issuer_name: str      # "StolperFrei Bodenverlegung GmbH"
    invoice_date: date | None
    policy_text: str
    damage_text: str
    items: tuple[LineItem, ...]
    images: tuple[Path, ...]
```

Extraction ladder, first success wins, each step ≤ 400 ms:

1. **PyMuPDF `page.get_text("dict")`** — word boxes with x-coordinates. Cluster
   x-positions into columns using the header row (`POS. DESCRIPTION QTY UNIT UNIT
   PRICE VAT TOTAL`) as the column ruler. This is the primary path and handles the
   observed layout exactly, because the file is a renderer-generated PDF with real
   text.
2. **`pdftotext -layout`** — whitespace-preserving; regex `^\s*(\d+)\s+(.+?)\s+([\d.,]+)\s+(m²|m2|lm|lfm|h|Std|pcs|Stk|St|pauschal|flat)\s*$`.
3. **pdfplumber `extract_table()`** — slow (~1–2 s) but survives ruled tables.
4. **Rasterise at 200 dpi → vision model OCR** — last resort, ~6 s, only on the slow
   path, only if 1–3 all returned zero rows.

Hard-won details that will actually bite:

- **Encoding.** Force UTF-8 everywhere, and read `policy.txt`/`description.txt` with
  `errors="replace"` after a `charset-normalizer` sniff — a `UnicodeDecodeError` at
  T+3 s on a cp1252 file with a `ß` in it is a lost game. Normalise `m²`→`SQM` via
  `unicodedata.normalize("NFKC")` first, which folds `²`→`2`.
- **Decimal comma.** German number formatting will appear somewhere (`18,5 m²`,
  `1.250,00`). Parse with a single function that tries `de_DE` then `en_US` and
  prefers the interpretation with ≤ 3 decimals.
- **Multi-page.** Repeat the header-row detection per page; carry the column ruler
  from page 1. Drop rows whose `pos` is not monotone increasing (page headers/footers
  that look like rows).
- **Sub-totals and non-items.** Rows matching `Net|Zwischensumme|plus VAT|Total
  amount|MwSt|Summe` are **not line items**. Getting the index alignment wrong shifts
  every `a` and `b` by one position and costs the whole game. Assert
  `len(items) == max_pos` and alert loudly if not.
- **Unit normalisation** is a table, not a model:
  `m²|m2|sqm|qm → SQM`, `lm|lfm|m|rm|running m → LM`,
  `pcs|Stk|St|St.|piece|ea|Stück → EACH`, `h|hrs|Std|Stunde|hour → HOUR`,
  `d|Tag|day → DAY`, `AW → AW` (Kfz Arbeitswerte!), `pauschal|flat|lump|psch → FLAT`.
- **The unit is a type check on the KB.** If the KB entry for a canonical id is
  `SQM` and the invoice says `LM`, that is a signal, not an error — either we matched
  the wrong concept or the invoice is odd. Log it and widen σ.

**Test corpus.** D2 generates 30 synthetic invoices in the observed template (same
column headers, 1–3 pages, 1–12 items, German/English mixed, decimal commas, an
umlaut-heavy company name, a scanned/rasterised variant) and the extractor must hit
30/30 before the first game. This is the single highest-value test in the repo.

### 3.2 Canonicaliser (deterministic + tiny model, ~50 ms)

Maps `(trade, description, unit)` → `kb_id` plus a match confidence.

1. **Alias table lookup**, normalised (lowercase, strip punctuation, singularise).
   Every KB entry carries 5–15 aliases in English *and* German.
2. **Token overlap / rapidfuzz** against alias set, threshold 80.
3. **Embedding nearest-neighbour** over KB entry texts (embeddings precomputed at
   build time; the query embedding is one ~30 ms call, batched over all items).
4. **Fallback:** `TRADE.__DEFAULT__.<UNIT>` — a trade-and-unit-level generic band
   with a deliberately wide σ. Never fails, never returns nothing.

Confidence feeds σ: exact alias → σ from KB; fuzzy → σ × 1.25; generic fallback →
σ = 0.55.

### 3.3 Agent A — Coverage

**Reads:** `policy.txt` (whole, typically short), the item list (description + qty +
unit), and the trade. **Does not read** prices or the KB — it must not be able to
rationalise a number.

Prompt in outline:

> You are a German P&C claims adjuster performing a **Deckungsprüfung**. You are
> given an insurance policy and a list of invoice line items. For each item decide
> whether the policy covers this specific work.
>
> A German policy typically covers *the consequences* of the insured peril but
> excludes: the cause itself where the policy says so, wear and maintenance
> (`Verschleiß`, `Wartung`), gradual damage (`allmähliche Einwirkung`), pre-existing
> defects (`Baumängel`), betterment beyond restoration (`Neu für Alt`, upgrades),
> anything outside the insured location, and perils requiring a rider the policy does
> not name (`Elementarschäden`, `Rückstau`, `Grundwasser`).
>
> **Quote the exact clause** you relied on. If no clause addresses the item, say
> `UNSTATED` — do not invent an exclusion. Output JSON, one object per index.

```json
{"items":[{"index":0,"verdict":"COVERED","p_covered":0.95,
           "clause":"§2.1 Ersetzt werden Schäden an Bodenbelägen infolge bestimmungswidrig austretenden Leitungswassers.",
           "deductible":250,"sublimit":null,"note":""},
          {"index":3,"verdict":"NOT_COVERED","p_covered":0.08,
           "clause":"§3.4 Nicht versichert sind Schäden durch Grundwasser.",
           "deductible":null,"sublimit":null,"note":"cellar item, peril excluded"}]}
```

Design rules that matter:

- **`UNSTATED` defaults to covered at p ≈ 0.75.** Hallucinated exclusions are
  catastrophic: they drive `b` to 0 (see §3.6) and we wrongfully reject and pay
  `1.5a`. The gate must be *reluctant*. Requiring a verbatim clause quote is the
  mechanism — a model that must paste the sentence hallucinates far less than one
  that must merely assert.
- **Deductible / sublimit are captured but not applied.** `t` is per line item and
  described as "the max a claims expert would consider appropriate" — an
  excess is a settlement-level concept, not a line-item price ceiling. Record it,
  do not subtract it, revisit if R9 says otherwise.
- **This gate is the one that can be run on a small fast model**, because it is
  extraction-with-judgement over a short document, not open-ended reasoning.

### 3.4 Agent B — Relatedness (+ quantity plausibility)

**Reads:** `description.txt`, the item list, and `images.png` when present.
**Does not read** the policy or prices.

> You are checking **Kausalität und Plausibilität**. Given a damage description and
> optionally a photograph, decide for each invoice line item whether the work is
> plausibly caused by, and proportionate to, the described damage.
>
> Flag `UNRELATED` when the item belongs to a different room, a different peril, or a
> different trade than the description supports. Flag `SCOPE_EXCESSIVE` when the item
> is related but the quantity or specification exceeds what the description implies
> (a whole-flat quantity for a single-room loss; premium material where the loss was
> standard; work on undamaged parts). Quote the sentence you relied on.

```json
{"items":[{"index":2,"verdict":"RELATED","p_related":0.90,
           "evidence":"\"...the living room floor was soaked over roughly 18 m².\"",
           "qty_verdict":"SUSPECT","qty_expected":[17.0,21.5],"qty_factor":0.86,
           "reason":"25 lm of skirting implies a 6:1 room for an 18 m² area"}]}
```

**The geometry check is deterministic and belongs in code, not the prompt.** For a
rectangular room of area `A` and aspect ratio `r`, the perimeter is
`P(r) = 2(√(A·r) + √(A/r))`:

| Area | square | 2:1 | 3:1 | 4:1 | 6:1 |
| --- | --- | --- | --- | --- | --- |
| 18 m² | 17.0 m | 18.0 m | 19.6 m | 21.2 m | 24.5 m |
| 25 m² | 20.0 m | 21.2 m | 23.1 m | 25.0 m | 28.9 m |
| 40 m² | 25.3 m | 26.8 m | 29.2 m | 31.6 m | 36.5 m |

So on the slide's own case, **25 lm of skirting against 18 m² of floor sits at the
extreme tail** — a 6:1 room, or an L-shape with several door reveals. That is exactly
the kind of quiet quantity inflation a real adjuster catches and a "what's a fair
price?" prompt does not. Rule: `qty_factor = clip(P_max(4:1) / qty_claimed, 0.7, 1.0)`
applied multiplicatively to `t̂`, and σ widened by 20%.

**Honest caveat, and it is a real one.** We do not yet know whether the generator
inflates *quantities* at all. Because `QTY` is printed for everyone, the more likely
generator design is `t = qty × fair_unit_price` with fraud injected through
*uncovered* and *unrelated* items rather than through quantities. So: ship the
geometry check with a **weight of 0.3** on day one, and let R9 decide. If settled
brackets show `t` tracking the printed quantity exactly even on absurd quantities,
set the weight to 0 in one line and move on. Do not let a beautiful check cost us
money.

**On images (§6 has the latency numbers).** F5 established that the photograph is a
stock image and may not even match the room. Therefore images feed **relatedness
only**, never price, and only in three ways: (i) does the depicted peril match the
described peril — water vs fire vs impact vs vehicle; (ii) does the depicted room
type match the invoiced room; (iii) is the depicted damage *categorically* severe
(structure exposed, screed visible, ceiling down) or *cosmetic* (staining, single
surface). Those three answers move `π_rel` and shift the price band by at most
±20% between a cosmetic and a structural read. Nothing more. Anyone building a
"measure the room from the photo" feature is burning latency on noise.

### 3.5 Agent C — Price build-up

**Reads:** item text, `qty`, `unit`, `trade`, and the KB entry with its build-up.
**Does not read** the policy (coverage is not its job) and **cannot output a free
number** — it outputs a *multiplier on the KB band*, clamped to `[0.6, 1.6]`.

> You are a German **Kalkulator**. Here is the invoice line item, and here is the
> standard cost basis for this work from our rate card, expressed as a net price per
> unit built from `Material + Stundensatz × Zeitansatz`.
>
> Your job is **not** to price the item from scratch. It is to decide whether this
> specific wording justifies moving off the standard band, and by how much. Reasons to
> move up: explicit premium specification, difficult access, small quantity (setup
> cost dominates), emergency/out-of-hours wording, contaminated or hazardous material.
> Reasons to move down: partial scope, basic specification, large quantity (volume
> discount), work already implied by another line item on this invoice.
>
> Output `factor ∈ [0.6, 1.6]` and one sentence of justification naming the driver.
> If nothing in the wording justifies a move, output `1.0`.

```json
{"items":[{"index":0,"kb_id":"FLOOR.LAMINATE.REMOVE","unit":"SQM","qty":18,
           "net_unit":{"lo":4.0,"mid":8.0,"hi":13.0},"sigma_log":0.28,
           "factor":1.15,"reason":"water-swollen laminate locks in the click joint; +15% handling",
           "buildup":"labour 0.10 h/m² x 48 EUR/h = 4.80 ; disposal 3.00 ; = 7.80 net/m²"}]}
```

Clamping the model to a bounded multiplier on a grounded band is the single most
important design decision in the pipeline. It gives us the LLM's genuine strength
(reading nuance in wording) while structurally denying it its genuine weakness
(producing an unanchored magnitude). **It is also what caps σ.** A free-form model
answer has σ ≈ 0.8–1.2; a KB band with σ = 0.25 and a ±60% clamp has σ ≈ 0.30. §2.3
prices that difference at roughly **+70% income**.

Two deterministic checks run alongside, in code:

- **Small-quantity surcharge.** Per-unit prices rise steeply on tiny jobs — one
  source's 1.85 m² screed removal came to 340 €/m² against a 50 €/m² headline. Apply
  `f_small = 1 + 0.8·max(0, 1 − qty/qty_ref)` with `qty_ref` per unit type
  (SQM: 15, LM: 20, EACH: 3), and enforce a per-line **minimum call-out floor** of
  ~`Anfahrtspauschale + 1 h` when the computed total falls below it.
- **Double-count detector.** If two line items on the same invoice map to KB ids
  flagged as overlapping (e.g. `FLOOR.LAMINATE.INSTALL` already includes underlay,
  and a separate `FLOOR.UNDERLAY` line appears), the second one's band is reduced to
  its *marginal* content only. `Doppelabrechnung` is the classic German
  `Kürzungsgrund` and the generator, being LLM-written, will produce it.

### 3.6 Posterior assembly and the decision rule (deterministic, ~1 ms)

Let `π = p_covered × p_related` and `π₀ = 1 − π`. Then

```
t  ~  π₀ · δ(0)  +  π · LogNormal(μ, σ)

μ = ln( qty · f_small · factor · κ_qty · net_unit_mid · κ_R9 · 1.19 )      # 1.19 = VAT
σ = sqrt( σ_kb² + σ_match² + σ_agent² )
```

**Reviewer (R4):** `b = Q₁ᐟ₃(t)` of the *mixture*, which has a beautiful closed form:

```
b = 0                                          if π₀ ≥ 1/3
b = exp( μ + σ · Φ⁻¹( (1/3 − π₀) / π ) )       otherwise
```

The mixture arithmetic gives us "reject uncovered items outright" **for free** — no
special case, no if-statement in the strategy. A coverage probability below 2/3
automatically drives `b` to zero. That is the same 2/3 the README derived from the
payoff matrix, arriving from a completely different direction, and it is a very
satisfying thing to have on a slide.

**Issuer (R5b), with the measured `p(a)`:**

```
a* = argmax_a  [ a·G(a) + min(a,c)·(1 − G(a))·p(a) ]
```

evaluated on a 200-point log-grid — 200 float ops, microseconds. Two regimes, and the
controller picks by measured `p`, not by mood:

- `π₀ ≥ 0.5` (uncovered/unrelated): **`a` = the *ungated* price estimate** (§2.4) —
  set `π = 1` and take the mode of the price posterior. This is where opponents' `b`
  is densest.
- otherwise: the grid optimum, which lands at ≈ `0.76 × median` overnight and marches
  out toward `c` as `p` rises. And `c` itself is bounded below by `4·t̂`, which we
  have — so the aggressive arm has a target, not a guess.

### 3.7 Learning loop (R9), between games — 12 minutes of slack per game

Per settled game, the leaderboard inversion yields `t ∈ [max fair a, min fraud a)`
per line item, plus an upper bound `t ≤ c/4` whenever anyone overshoots the cap.
Feed those into two estimators:

1. **Global scale `κ_R9`** — one number, updated after every game. If our `t̂` is
   systematically 1.3× the bracket midpoints, that is a units bug or a VAT bug, and it
   shows up in game 2, not game 40. *This alone justifies the R9 work.*
2. **Per-`kb_id` correction** — a hierarchical shrinkage estimator, `κ_item` pooled
   toward `κ_trade` pooled toward `κ_R9`, with the pooling weight set by the number of
   observations. By Sunday morning the frequent items (laminate, painting per m²,
   plumbing hours, windscreen) are near-exact and the rare ones still ride the prior.
3. **σ calibration (R4b)** — the *only* legitimate way to set the interval width.
   Plot realised bracket position against predicted quantile; if 60% of observed `t`
   fall inside our nominal 80% interval, σ is too narrow — scale it up globally until
   empirical coverage matches nominal. This plot is also the best single slide in the
   pitch.

---

## 4. The price knowledge base

This is the durable asset. It works from game 1 with zero labels, it is the thing R9
shrinks toward, and it is the artefact that makes the write-up credible.

### 4.0 Three conventions, decided once, never revisited

**(a) Everything is stored NET. Gross-up happens exactly once, at the last line of
posterior assembly, as `× 1.19`.** German VAT on Handwerkerleistungen is 19%; no
reduced rate applies to repair work. The invoice's own `Net / plus VAT / Total amount`
footer (F3) says the generator works the same way. One `× 1.19`, one place, one test.

**(b) Consumer portals quote GROSS; trade publications quote NET.** This is not a
guess — under the German **Preisangabenverordnung (PAngV)** a tradesperson must quote
a consumer the gross price, and may not even write "350 € zzgl. MwSt" in a
consumer-facing offer ([MyHammer trade blog](https://www.my-hammer.de/blog/bruttopreis-pflicht-warum-sie-keine-nettopreise-nennen-duerfen)).
So MyHammer, Check24, Aroundhome, Blauarbeit, Kostencheck and trustlocal figures are
divided by 1.19 before entering the KB; angebots-meister, clean-invoice and repleno
state NET explicitly and enter as-is. **Every KB row records which it was.** Getting
this backwards is a uniform 19% error in `t̂` — the single most likely catastrophic
bug in the whole build, and the reason it is convention (a).

**(c) A market €/unit anchor beats an hourly build-up. Always.** The temptation is to
compute labour from laying speed: a floor layer does 15–25 m²/h of laminate, at 52 €/h
that is ~2.6 €/m². The market says 18–28 €/m² net. The gap is a factor of **eight**,
and it is not fraud — it is preparation, cutting, waste, edging, setup, travel,
tooling, insurance, overhead and margin, which a €/m² unit rate contains and a raw
labour-minute does not. So: **`Stundensatz × Zeitansatz` is the *sanity check and the
explanation*, never the primary estimate**, and it is used as the primary estimate
only for the handful of items genuinely billed by the hour (`HOUR` unit, call-outs,
`AW` in Kfz). Every KB row carries both, and a `overhead_factor` field records the
ratio so the build-up reconciles.

### 4.1 Schema

```yaml
# kb/flooring.yaml
- id: FLOOR.LAMINATE.INSTALL_INCL_UNDERLAY
  trade: Flooring
  label_en: "Install laminate incl. impact sound insulation"
  label_de: "Laminat verlegen inkl. Trittschalldämmung"
  unit: SQM
  includes_material: true
  net_unit_eur: {lo: 29.0, mid: 39.0, hi: 55.0}   # NET, per unit, DE national 2026
  sigma_log: 0.22
  build_up:
    labour_rate_eur_h: 52.0        # Bodenleger, Geselle, net, national
    hours_per_unit: 0.42           # implied; raw laying speed is ~0.07 h/m²
    overhead_factor: 6.0           # market rate / raw labour-minute  (see 4.0c)
    material_eur_unit: 14.0        # AC4 laminate
    consumables_eur_unit: 3.5      # underlay + vapour barrier + tape
  qty_ref: 15                      # small-job surcharge reference quantity
  overlaps: [FLOOR.UNDERLAY]       # double-count detector
  aliases:
    - "new installation of laminate incl. impact sound insulation"
    - "lay laminate flooring"
    - "install laminate with underlay"
    - "Laminat neu verlegen"
    - "Neuverlegung Laminat inkl. Trittschall"
  sources:
    - {ref: "angebots-meister 2026", figure: "18-28 EUR/m2 labour NET; AC4 8-20; Trittschall 2-5", basis: NET,
       url: "https://angebots-meister.de/blog/laminat-verlegen-kosten-2026"}
    - {ref: "trustlocal 2026", figure: "20-40 EUR/m2 laying, 5-75 material", basis: GROSS,
       url: "https://trustlocal.de/kosten/bodenleger-kosten/"}
    - {ref: "CHECK24", figure: "18 EUR/m2 laying + 15 material + 1 underlay", basis: GROSS,
       url: "https://handwerk.check24.de/craftsmen/kosten/laminatverleger"}
  notes: >
    Cross-check: angebots-meister complete package for 20 m2 is 1050-1430 EUR GROSS
    incl. skirting; our 18 m2 build-up excl. skirting gives 878 EUR gross. Consistent.
```

Four sidecar tables, same file format:

```yaml
# kb/rates.yaml — net customer-facing Stundenverrechnungssatz, Geselle level, DE 2026
# kb/regions.yaml — multiplier by location token found in policy/description
# kb/surcharges.yaml — out-of-hours, emergency, access, small job, hazardous
# kb/units.yaml — the normalisation table from 3.1
```

### 4.2 Seed table — hourly rates (NET €/h, national, Geselle)

Primary source [repleno 2026](https://repleno.com/de/blog/was-kostet-meister-gesellenstunde)
(explicitly net, 2024 base + 2026 projection), cross-checked against
[angebots-meister](https://angebots-meister.de/blog/malerarbeiten-preise-2026) (net),
[clean-invoice](https://www.clean-invoice.com/wissen/allgemein/handwerker-stundenlohn-kosten-2026)
(net) and [trustlocal](https://trustlocal.de/kosten/bodenleger-kosten/) (gross, ÷1.19).

| Trade (`TRADE` field) | German | lo | **mid** | hi | Notes |
| --- | --- | --- | --- | --- | --- |
| Painting | Maler / Lackierer | 48 | **58** | 70 | repleno 62; angebots-meister 48–62 avg |
| Flooring | Bodenleger / Parkettleger | 42 | **52** | 65 | trustlocal 40–60 gross → 34–50 net; a-m Geselle 42–58 net |
| Tiling | Fliesenleger | 45 | **56** | 68 | repleno 58 |
| Drywall | Trockenbauer | 42 | **52** | 65 | repleno 50 |
| Screed | Estrichleger | 45 | **58** | 75 | profirechner 45–90 |
| Electrical | Elektrotechnik | 52 | **66** | 82 | repleno 64; 2026 Geselle 68–71, Meister 75–85 |
| Plumbing / HVAC | SHK / Installateur | 55 | **68** | 85 | repleno 65; 2026 Geselle 68–72, Meister 75–82 |
| Carpentry | Tischler / Schreiner | 50 | **62** | 76 | repleno 63 |
| Masonry | Maurer | 48 | **60** | 74 | repleno 60 |
| Roofing | Dachdecker / Zimmerer | 55 | **68** | 84 | repleno 68; 2026 Geselle 72–75 |
| Glazing | Glaser | 48 | **60** | 74 | interpolated from adjacent trades |
| Metalwork | Schlosser / Metallbau | 52 | **64** | 80 | repleno 65 (with SHK) |
| Landscaping | GaLaBau | 42 | **52** | 64 | repleno 52 |
| Cleaning | Gebäudereinigung | 30 | **38** | 48 | repleno 38 |

Modifiers, applied multiplicatively:

| Modifier | Factor | Source |
| --- | --- | --- |
| Meister rather than Geselle | **×1.15** | repleno: Geselle 65–70, Meister 72–78 net |
| Helfer / Azubi | **×0.70** | angebots-meister: Helfer 30–40 vs Geselle 42–58 net |
| München / Hamburg / Frankfurt / BW | **×1.20** | clean-invoice +15–25%; bodendesign +20–30% metro |
| East Germany (SN, TH, ST, MV, BB) | **×0.85** | 54 € Ost vs 64 € West = −15.6% |
| Saturday | **×1.35** | +25–50% |
| Sunday / night | **×1.75** | +50–100% |
| Public holiday | **×2.25** | +100–150% |
| Emergency call-out (`Notdienst`) | **×1.75** + 80–150 € flat | electrician sources: typical 200–400 € for first hour |
| Small job (`qty` below `qty_ref`) | `1 + 0.8·(1 − qty/qty_ref)` | kostencheck: 1.85 m² screed job → 340 €/m² vs 50 €/m² headline |

Call-out / travel (`Anfahrtspauschale`): **net [18, 30, 55] €** flat, or 0.25–0.85 €/km
net; up to 25 km typically 38–84 € net.

### 4.3 Seed table — Flooring (the slide's own trade), NET €/unit

| `kb_id` | Item | Unit | lo | **mid** | hi | σ<sub>log</sub> | Anchors (basis) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FLOOR.LAMINATE.REMOVE` | Remove + dispose laminate | SQM | 4.0 | **8.0** | 13.0 | 0.28 | MyHammer 3–8 G; trustlocal 2–8 G; a-m 10 N incl. adhesive |
| `FLOOR.LAMINATE.INSTALL_LABOUR` | Lay laminate, labour only | SQM | 15 | **21** | 30 | 0.24 | a-m 18–28 N; CHECK24 18 G; trustlocal 20–40 G |
| `FLOOR.LAMINATE.MATERIAL` | Laminate AC3–AC4 | SQM | 8 | **14** | 24 | 0.32 | a-m 8–20 N (AC5 18–35 N); aroundhome 5–30 G |
| `FLOOR.UNDERLAY` | Impact-sound underlay, supplied + laid | SQM | 2.0 | **3.5** | 6.5 | 0.30 | a-m 2–5 N std / 5–9 N premium; trustlocal 0.5–5 + 1–2 G |
| **`FLOOR.LAMINATE.INSTALL_INCL_UNDERLAY`** | Lay laminate incl. underlay + material | SQM | 29 | **39** | 55 | 0.22 | sum of the three above; clean-invoice 27–55 N |
| `FLOOR.LAMINATE.DIAGONAL` | …laid diagonal | SQM | 36 | **48** | 68 | 0.24 | a-m labour 25–38 N |
| `FLOOR.LAMINATE.HERRINGBONE` | …herringbone / chevron | SQM | 48 | **68** | 95 | 0.28 | a-m labour 32–60 N |
| `FLOOR.SKIRTING.REPLACE` | Remove old + supply + fit MDF skirting | LM | 5.0 | **8.5** | 14.0 | 0.30 | remove 1–3 G; MDF 2–4 N; fit 2–8 G; complete 8–35 G |
| `FLOOR.SKIRTING.SOLIDWOOD` | …solid timber skirting | LM | 12 | **19** | 30 | 0.32 | a-m Vollholz 6–18 N + fit |
| `FLOOR.TRANSITION_PROFILE` | Transition / threshold strip | EACH | 10 | **18** | 30 | 0.35 | a-m alu 12–25 N; bodendesign 5–15 G |
| `FLOOR.DOORFRAME.TRIM` | Undercut door frame | EACH | 13 | **19** | 28 | 0.28 | bodendesign 15–30 G |
| `FLOOR.SUBFLOOR.PREP` | Level / fill / sand subfloor | SQM | 8 | **15** | 26 | 0.34 | aroundhome 8–50 G; trustlocal 15–35 G; a-m 12 N |
| `FLOOR.PRIMER` | Primer coat to subfloor | SQM | 2.5 | **4.0** | 6.0 | 0.26 | a-m 4 N |
| `FLOOR.PARQUET.INSTALL_LABOUR` | Lay parquet, labour | SQM | 25 | **34** | 45 | 0.26 | trustlocal 30–50 G (pattern 45–60 G) |
| `FLOOR.PARQUET.MATERIAL` | Parquet, engineered → solid | SQM | 22 | **50** | 110 | 0.55 | trustlocal 25–150 G |
| `FLOOR.PARQUET.SAND_SEAL` | Sand + seal parquet | SQM | 25 | **32** | 42 | 0.24 | parkett-schliff 30–45; +5–15 water-damage uplift |
| `FLOOR.PARQUET.SAND_ONLY` | Sand only | SQM | 13 | **17** | 22 | 0.24 | parkett-schliff 15–25 |
| `FLOOR.VINYL.INSTALL_CLICK` | Lay click vinyl / LVT | SQM | 13 | **18** | 25 | 0.26 | bodendesign 15–30 G |
| `FLOOR.VINYL.INSTALL_GLUE` | Lay glue-down vinyl | SQM | 17 | **23** | 30 | 0.26 | bodendesign 20–35 G |
| `FLOOR.VINYL.MATERIAL` | Vinyl / design floor | SQM | 13 | **26** | 60 | 0.45 | bodendesign 15–80 G |
| `FLOOR.CARPET.INSTALL` | Lay carpet, fully bonded | SQM | 8 | **13** | 20 | 0.28 | trustlocal 10–20 G; bodenleger.net 10–25 G |
| `FLOOR.CARPET.REMOVE` | Lift + dispose carpet | SQM | 3.0 | **7.0** | 15.0 | 0.42 | blauarbeit loose 3–6, bonded 5–12, old adhesive 10–20 |
| `FLOOR.TILE.INSTALL_LABOUR` | Lay floor tiles, labour | SQM | 42 | **55** | 68 | 0.22 | aroundhome 50–80 G |
| `FLOOR.TILE.MATERIAL` | Floor tiles | SQM | 9 | **30** | 85 | 0.60 | aroundhome 10–100 G |
| `FLOOR.TILE.REMOVE` | Break out + dispose tiles | SQM | 13 | **22** | 38 | 0.34 | MyHammer 15–45 G; aroundhome ~20 G |
| `FLOOR.TILE.SILICONE` | Silicone joint | LM | 2.5 | **3.5** | 5.0 | 0.24 | aroundhome 3–5 G |
| `SCREED.REMOVE` | Break out cement screed | SQM | 16 | **28** | 48 | 0.38 | blauarbeit 18–40; kostencheck 25–60 G incl. disposal |
| `SCREED.REMOVE_DRY` | Lift dry screed boards | SQM | 8 | **13** | 19 | 0.30 | blauarbeit 8–18 |
| `SCREED.INSULATION.REMOVE` | Remove insulation / membrane below screed | SQM | 5 | **8** | 12 | 0.30 | blauarbeit 5–12 |
| `SCREED.LAY_CEMENT` | New cement screed incl. insulation | SQM | 19 | **27** | 42 | 0.30 | blauarbeit 20–50; profirechner |
| `SCREED.LAY_FLOWING` | Calcium-sulphate / flowing screed | SQM | 24 | **32** | 47 | 0.26 | blauarbeit 26–55 |
| `SCREED.LEVELLING` | Levelling compound | SQM | 7 | **13** | 21 | 0.32 | blauarbeit 8–25 |
| `DRYWALL.PARTITION` | Stud partition, plasterboard, incl. material | SQM | 30 | **42** | 65 | 0.30 | blauarbeit 35–80 G; daibau 40–70 |
| `DRYWALL.CEILING_SUSPEND` | Suspended plasterboard ceiling | SQM | 28 | **46** | 90 | 0.42 | blauarbeit/aroundhome 30–120 G |
| `DRYWALL.LINING` | Wall lining / Vorsatzschale | SQM | 25 | **38** | 50 | 0.28 | blauarbeit 30–60 G |
| `DRYWALL.FILL_Q3` | Fill + sand to Q3 | SQM | 7 | **9** | 13 | 0.26 | blauarbeit 8–15 G |
| `DISPOSAL.RUBBLE` | Construction waste disposal | M3 | 27 | **42** | 76 | 0.36 | MyHammer 30–90 G |
| `DISPOSAL.CONTAINER_5M3` | 5 m³ skip, delivered + collected | FLAT | 170 | **230** | 295 | 0.24 | MyHammer 200–350 G |
| `DISPOSAL.BIGBAG_1M3` | 1 m³ big bag | EACH | 42 | **63** | 84 | 0.26 | kostencheck 50–100 G |
| `SITE.DUST_PROTECTION` | Dust screening / containment | FLAT | 70 | **125** | 210 | 0.36 | blauarbeit 80–250 |
| `SITE.TRAVEL` | Call-out / travel | FLAT | 18 | **30** | 55 | 0.34 | trustlocal/aroundhome 20–65 G |

Cross-item surcharges to encode as `factor` hints for Agent C:

- Pipes / conduits embedded in the screed being removed: **+30–50%** on the line.
- Contaminated or hazardous material handling (asbestos-suspect adhesive): **+20–30%**,
  plus a `MATERIAL.LAB_SAMPLE` line at 42–170 € net per sample.
- Water-swollen laminate/parquet versus dry removal: **+15%** (click joints lock,
  boards delaminate) — parkett-schliff quotes an explicit 5–15 €/m² water-damage
  uplift on sanding work.

### 4.4 Seed table — Painting & decorating, NET €/unit

All figures from [angebots-meister Malerarbeiten 2026](https://angebots-meister.de/blog/malerarbeiten-preise-2026),
which states **netto, 19% MwSt kommt hinzu** — the cleanest single source we found.

| `kb_id` | Item | Unit | lo | **mid** | hi | σ<sub>log</sub> |
| --- | --- | --- | --- | --- | --- | --- |
| `PAINT.WALL_2COAT` | Paint wall, two coats | SQM | 8 | **11** | 14 | 0.20 |
| `PAINT.WALL_PRIMED` | Paint wall incl. primer | SQM | 10 | **13** | 16 | 0.20 |
| `PAINT.WALL_STRONG_COLOUR` | Strong / saturated colour | SQM | 12 | **15** | 18 | 0.20 |
| `PAINT.WALL_OLDBUILD` | Old building, with preparation | SQM | 12 | **16** | 20 | 0.24 |
| `PAINT.CEILING_2COAT` | Paint ceiling, two coats | SQM | 10 | **13** | 16 | 0.20 |
| `PAINT.PRIMER` | Deep primer (`Tiefgrund`) | SQM | 2 | **3** | 4 | 0.22 |
| `PAINT.BARRIER_PRIMER` | Stain-block primer (`Sperrgrund`) — **the water-damage line** | SQM | 4 | **6** | 8 | 0.24 |
| `PAINT.WALLPAPER_REMOVE` | Strip wallpaper | SQM | 4 | **6** | 8 | 0.26 |
| `PAINT.WALLPAPER_REMOVE_GLUE` | …incl. paste residue | SQM | 6 | **9** | 12 | 0.26 |
| `PAINT.WOODCHIP_HANG` | Hang woodchip (`Raufaser`) | SQM | 10 | **12.5** | 15 | 0.20 |
| `PAINT.WOODCHIP_HANG_PAINT` | Hang woodchip + two coats | SQM | 16 | **20** | 24 | 0.20 |
| `PAINT.PATTERN_WALLPAPER` | Patterned wallpaper with repeat | SQM | 18 | **24** | 30 | 0.24 |
| `PAINT.FILL_Q2` | Skim to Q2 | SQM | 12 | **15** | 18 | 0.20 |
| `PAINT.FILL_Q3` | Skim to Q3 | SQM | 18 | **23** | 28 | 0.20 |
| `PAINT.FILL_Q4` | Skim to Q4 | SQM | 28 | **36** | 45 | 0.22 |
| `PAINT.MASK_COVER` | Masking + covering | SQM | 1.5 | **2.0** | 3.0 | 0.26 |
| `PAINT.DOOR_FRAME` | Paint door frame | EACH | 80 | **100** | 120 | 0.20 |
| `PAINT.DOOR_FRAME_STRIP` | …incl. stripping old paint | EACH | 120 | **150** | 180 | 0.20 |
| `PAINT.RADIATOR` | Paint radiator | SQM | 35 | **45** | 55 | 0.22 |
| `PAINT.FACADE_2COAT` | Façade, two coats | SQM | 18 | **23** | 28 | 0.20 |
| `PAINT.FACADE_PRIMED` | Façade incl. primer | SQM | 22 | **28** | 35 | 0.20 |
| `SITE.SCAFFOLD` | Scaffold standing charge | SQM | 6 | **9** | 12 | 0.26 |

Minimum order value for a painting job: **250–500 € net** — encode as a per-invoice
floor, not a per-line floor. Rush-job surcharge: **+25–50%**.


### 4.6 Seed table — Automotive (Kfz), NET €/unit

Kfz is a different economy from building trades and it deserves its own rules. It is
also the trade where our grounding advantage is largest, because the German motor
claims market has **published, court-tested rate schedules** that a language model
asked "what does it cost to respray a wing?" will never reproduce.

**Anchor: the DEKRA `Deutscher Reparatur-Stundensatz` (DRS)** — surveyed across >13,000
German workshops, published *explicitly net* ("Alle Angaben in Euro und ohne MwSt.").
It reconciles with the GDV's gross figures to within a rounding error
(GDV 2024 paint 220 € gross ÷ 1.19 = 184.9 € net ≈ DEKRA 2025 paint ~179 € net), which
is the cleanest cross-validation in the entire knowledge base.

| Rate (`Stundenverrechnungssatz`) | Unit | **National 2026** | München | Low (Cottbus/Chemnitz) | Basis |
| --- | --- | --- | --- | --- | --- |
| Mechanik | €/h | **141.43** | ~200.75 *(2025)* | 131.00 *(2025)* | **NET** |
| Karosserie | €/h | **173.94** | **235.75** | 145.75 | **NET** |
| Lackierung (labour, excl. paint material) | €/h | **192.87** | **243.00** | 165.25 | **NET** |

Source: [DEKRA DRS 2026 via schaden.news](https://schaden.news/de/article/link/44861/dekra-reparatur-stundensatz-steigt-2025-26-um-7-5-prozent);
gross cross-check [GDV 2024](https://www.gdv.de/gdv/medien/medieninformationen/autoreparaturen-teurer-denn-je-stundensatz-von-kfz-werkstaetten-erstmals-ueber-200-euro-193000)
(202 € mech/body, 220 € paint, **gross**). Year-on-year: **+7.5%** 2025→2026, **+9.5%**
2024→2025 — uprate any older figure accordingly.

> **Do not hard-code the München premium.** The invoice's `TO` address is a constant
> ("European Hackathon, Hauptstraße 1, 8000 Munich"), so it cannot discriminate between
> cases, and a Munich body rate is **+35%** over the national average. Seed the national
> figure and let `κ_R9` (§3.7) find the generator's actual level within five games.
> Guessing this wrong is a 35% error on every Kfz case; measuring it is free.

**`AW` — Arbeitswerte.** If the `UNIT` column says `AW`, the quantity is *not* hours.
The extractor must recognise it and the KB must convert:

| System | 1 AW = | AW per hour | €/AW at national Mechanik 141.43 net | Brands |
| --- | --- | --- | --- | --- |
| **10er** | 6 min | 10 | **14.14 €** | most importers, DAT/Audatex time units |
| **12er** | 5 min | 12 | **11.79 €** | **BMW, Mercedes-Benz** |
| **100er** | 36 s | 100 | **1.414 €** | **VW / Audi group** |

`labour = AW × (Stundenverrechnungssatz ÷ AW_per_hour)`. The €/AW is **not comparable
across brands** — always normalise to €/h before sanity-checking. When the brand is
unknown, assume 10er and widen σ to 0.35.

| `kb_id` | Item | Unit | lo | **mid** | hi | σ<sub>log</sub> | Basis / source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `KFZ.LABOUR.MECHANIC` | Mechanical labour | HOUR | 120 | **141** | 200 | 0.18 | DEKRA DRS 2026, NET |
| `KFZ.LABOUR.BODY` | Body-shop labour | HOUR | 146 | **174** | 236 | 0.18 | DEKRA DRS 2026, NET |
| `KFZ.LABOUR.PAINT` | Paint labour | HOUR | 165 | **193** | 243 | 0.16 | DEKRA DRS 2026, NET |
| `KFZ.PAINT.MATERIAL_SURCHARGE` | Paint material, % of paint labour | PCT | 30 | **35** | 45 | — | [IWW](https://www.iww.de/ue/schadenregulierung/reparaturkosten-der-lackmaterialzuschlag-ist-in-den-fokus-mancher-versicherer-geraten-f81992) — 30–40%, higher upheld in court |
| `KFZ.PAINT.WING` | Respray one wing (`Kotflügel`) | EACH | 210 | **355** | 670 | 0.34 | 250–800 G → ÷1.19 |
| `KFZ.PAINT.DOOR` | Respray one door | EACH | 210 | **420** | 840 | 0.36 | 250–1000 G |
| `KFZ.PAINT.BUMPER` | Respray bumper | EACH | 210 | **400** | 590 | 0.30 | 250–700 G |
| `KFZ.PAINT.BONNET` | Respray bonnet, compact | EACH | 336 | **640** | 825 | 0.32 | FairGarage 400–980 G |
| `KFZ.PAINT.BONNET_PREMIUM` | …premium segment (GLC/A8/5er) | EACH | 925 | **1010** | 1240 | 0.16 | FairGarage 1100–1475 G |
| `KFZ.PAINT.ROOF` | Respray roof | EACH | 336 | **590** | 760 | 0.28 | 400–900 G |
| `KFZ.PAINT.FULL` | Full respray, standard | EACH | 1680 | **2940** | 5040 | 0.38 | 2000–6000 G |
| `KFZ.PAINT.METALLIC_SURCHARGE` | Metallic / pearl surcharge | PCT | 20 | **28** | 40 | — | motor.com.de |
| `KFZ.PAINT.BLENDING` | `Beilackierung` of an adjacent panel | EACH | 84 | **170** | 252 | 0.34 | 100–300 |
| `KFZ.PAINT.SMART_REPAIR` | Spot / smart repair | EACH | 84 | **170** | 336 | 0.42 | 100–400 G; ADAC 40–80 G for a 25 mm scratch |
| `KFZ.DENT.PUSH` | Paintless dent removal, small | EACH | 25 | **65** | 126 | 0.44 | ADAC 30–150 G |
| `KFZ.DENT.PUSH_LARGE` | …medium/large | EACH | 126 | **270** | 420 | 0.36 | 150–500 G |
| `KFZ.GLASS.WINDSCREEN` | Windscreen, no driver assistance | EACH | 328 | **530** | 660 | 0.26 | Carglass ab 390 G; 631–786 G typical |
| `KFZ.GLASS.WINDSCREEN_ADAS` | Windscreen **with** assistance systems | EACH | 672 | **840** | 1050 | 0.22 | Carglass 800–1250 G |
| `KFZ.GLASS.ADAS_CALIBRATION` | ADAS calibration, static | EACH | 180 | **220** | 280 | 0.18 | **NET**, kfz-dietrich |
| `KFZ.GLASS.ADAS_CALIBRATION_DYN` | …static + dynamic | EACH | 250 | **310** | 390 | 0.18 | **NET**, kfz-dietrich |
| `KFZ.GLASS.CHIP_REPAIR` | Stone-chip repair, 1 impact | EACH | 130 | **155** | 180 | 0.14 | Carglass 184.45 G |
| `KFZ.GLASS.REAR` | Rear screen | EACH | 210 | **340** | 505 | 0.32 | 250–600 |
| `KFZ.BUMPER.FRONT_COMPACT` | Front bumper, compact (Golf VII), complete | EACH | 1817 | **1910** | 2006 | 0.12 | FairGarage 2162–2387 G |
| `KFZ.BUMPER.FRONT_PARKASSIST` | …with park-assist sensors | EACH | 2100 | **2275** | 2450 | 0.12 | FairGarage 2708 G |
| `KFZ.BUMPER.REAR_COMPACT` | Rear bumper, compact, complete | EACH | 1015 | **1125** | 1233 | 0.12 | FairGarage 1208–1467 G |
| `KFZ.BUMPER.FRONT_SMALL` | Front bumper, small car (Fiesta) | EACH | 610 | **695** | 782 | 0.14 | FairGarage 726–931 G |
| `KFZ.MIRROR.GLASS` | Mirror glass only | EACH | 45 | **96** | 214 | 0.42 | FairGarage 54–255 G |
| `KFZ.MIRROR.COMPLETE` | Complete wing mirror incl. paint | EACH | 303 | **505** | 668 | 0.26 | FairGarage 361–795 G |
| `KFZ.HEADLAMP.HALOGEN` | Halogen headlamp, part | EACH | 67 | **140** | 210 | 0.42 | 80–250 |
| `KFZ.HEADLAMP.XENON` | Xenon headlamp, part | EACH | 420 | **840** | 1260 | 0.40 | 500–1500 |
| `KFZ.HEADLAMP.LED_MATRIX` | LED / matrix-LED headlamp | EACH | 1680 | **2900** | 4800 | 0.38 | ADAC 2000–5700 |
| `KFZ.PDC_SENSOR` | Parking sensor | EACH | 71 | **140** | 210 | 0.36 | 85–250 |
| `KFZ.DOOR.REPLACE` | Door replacement incl. paint | EACH | 1260 | **1890** | 2520 | 0.30 | 1500–3000 |
| `KFZ.WING.REPLACE` | Wing replacement incl. paint | EACH | 670 | **1180** | 1680 | 0.32 | 800–2000 |
| `KFZ.TRANSFER` | `Verbringungskosten` to paint shop | FLAT | 50 | **105** | 250 | 0.40 | 100–150 typical; 251.97 **net** upheld in court |
| `KFZ.UPE_SURCHARGE` | `UPE-Aufschlag` on net parts | PCT | 10 | **13** | 20 | — | payable in fictitious settlement if regionally customary (BGH) |
| `KFZ.TOW` | Recovery / towing, up to 10 km | FLAT | 101 | **155** | 230 | 0.28 | 120–210 G; 230 **net** upheld (AG München) |
| `KFZ.TOW_PER_KM` | …per additional km | FLAT | 1.3 | **2.5** | 3.0 | 0.30 | |
| `KFZ.STORAGE` | Workshop standing charge | DAY | 7 | **12** | 16 | 0.26 | outdoor 7–8, indoor 10–16 |
| `KFZ.HU_AU` | Roadworthiness test HU + AU | EACH | 88 | **137** | 143 | 0.12 | ADAC 163 G national average |
| `KFZ.SERVICE_SMALL` | Minor service | EACH | 126 | **230** | 378 | 0.32 | 150–450 G |
| `KFZ.SERVICE_LARGE` | Major service | EACH | 250 | **500** | 672 | 0.30 | 400–800 G |
| `KFZ.TYRE_FIT` | Fit + balance one wheel | EACH | 9 | **20** | 50 | 0.40 | 10–60 G |

**Non-repair heads that appear on German motor claims** — and the trap they carry:

| `kb_id` | Item | Unit | lo | **mid** | hi | `vat_applies` |
| --- | --- | --- | --- | --- | --- | --- |
| `KFZ.EXPERT_FEE` | `Sachverständigenhonorar`, BVSK HB-V | FLAT | see table | see table | see table | **true** |
| `KFZ.LOSS_OF_USE` | `Nutzungsausfallentschädigung` | DAY | 23 (grp A) | **35** (grp C, Golf) | 175 (grp L) | **false** ⚠ |
| `KFZ.HIRE_CAR` | `Mietwagen`, class 5 | DAY | 25 | **45** | 66 | true |
| `KFZ.DIMINUTION` | `Merkantile Wertminderung` | FLAT | Ruhkopf/Sahm | — | — | **false** ⚠ |
| `KFZ.EXPENSES_FLAT` | `Auslagen-/Unkostenpauschale` | FLAT | 20 | **25** | 30 | **false** ⚠ |

> **⚠ The VAT trap.** `Nutzungsausfall`, `merkantile Wertminderung` and the
> `Auslagenpauschale` are **compensation, not supply** — they carry **no VAT**. A
> pipeline that blindly multiplies every line by 1.19 overcharges these by 19% and
> lands squarely in the fraud zone on items whose fair value is *known exactly from a
> published table*. Hence the per-row `vat_applies` field in §4.1. This is the kind of
> detail that separates a claims system from a pricing prompt, and it is worth a line
> in the write-up.

**BVSK 2024 expert-fee schedule (NET, HB-V corridor)** — keyed on net repair cost plus
diminution, always rounding *up* to the next band
([BVSK Honorartabelle 2024](https://kfzgutachter-breinlinger.de/wp-content/uploads/2025/03/Honorartabelle_2024.pdf)):

| Damage up to | 500 | 1 000 | 2 000 | 3 000 | 5 000 | 10 000 | 15 000 | 20 000 | 30 000 | 50 000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Fee (HB V, net €)** | 265–306 | 354–399 | 491–545 | 588–651 | 756–830 | 1063–1166 | 1376–1510 | 1653–1806 | 2218–2434 | 3464–3738 |

Ancillaries, net: photo 1st set **2.00 €**/image, 2nd set 0.50 €; mileage **0.70 €/km**;
typing 1.80 €/page; postage/phone **15.00 €** flat; axle measurement 132–140 €; body
measurement 252–272 €; fault-code read-out 59–74 €.

**`Nutzungsausfall` (Sanden/Danner/Küppersbusch), € per calendar day, no VAT** — a
*published table*, therefore a line item whose `t` we can hit almost exactly:

| Grp | A | B | C | D | E | F | G | H | J | K | L |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| €/day | 23 | 29 | **35** | 38 | 43 | 50 | 59 | 65 | 79 | 119 | 175 |
| Example | Up, Panda | Polo, Fiesta | **Golf, Focus** | A3, Octavia | Passat, 318i | A4, C-Klasse | A6, 5er | E-Klasse | X5, Q7 | 911 Carrera | 911 Turbo, SL |

There is **no group "I"**. Vehicle over 5 years → one group down; over 10 years → two
groups down. (Several SEO sites publish a shifted table that invents a group I — do not
ingest them.)

**Cross-cutting Kfz rules to encode as Agent C hints:**

- **Front bumpers cost 1.3–1.8× rear bumpers** on the same model — radar, camera and
  grille integration. A front/rear price parity on an invoice is a mispricing signal.
- **Any windscreen on an EU car registered from Nov 2022 needs ADAS calibration**
  (+180–390 € net). A windscreen line with no calibration line is *under*-invoiced;
  a calibration line on a 2008 car is unrelated.
- **Visible body panels inflate faster than mechanical parts** (German `Designschutz`
  gives OEMs a monopoly on visible parts to 2045): GDV Oct 2025 measured all parts
  +6% year-on-year but **front doors and bonnets +8%**, and tailgates and rear quarter
  panels roughly **doubled since 2015**.
- **`Bagatellschadengrenze`** (below which an expert report is not reimbursable) has no
  statutory value: 750 € is the orientation figure, but courts have set 500 € (AG
  Bautzen 2025) and 1 000 € (AG München 2024). Model as a range, not a constant.

### 4.7 Worked example — QuantCo's own slide, end to end

The invoice in §0, priced by this knowledge base. `TRADE = Flooring` → Bodenleger rate
card. Every figure net until the final `× 1.19`.

| Pos | Item | qty | unit | `kb_id` | net/unit | net line | **gross line** | gates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Remove water-damaged laminate, living room | 18 | m² | `FLOOR.LAMINATE.REMOVE` | 8.00 × **1.15** *(water-swollen: click joints lock)* = 9.20 | 165.60 | **197.06** | covered ✓ related ✓ |
| 2 | New laminate incl. impact sound insulation | 18 | m² | `FLOOR.LAMINATE.INSTALL_INCL_UNDERLAY` | 39.00 | 702.00 | **835.38** | covered ✓ related ✓ |
| 3 | Replace skirting boards | 25 | lm | `FLOOR.SKIRTING.REPLACE` | 8.50 × **0.86** *(geometry flag)* = 7.31 | 182.75 | **217.47** | covered ✓ **qty SUSPECT** |
| | | | | | **Net 1 050.35** | **plus VAT 199.57** | **Total 1 249.92** | |

Build-up behind Pos 2, which is what we show QuantCo:

```
labour  (Bodenleger, national, net)           21.00 €/m²
material laminate AC4                         14.00 €/m²
underlay + vapour barrier, supplied and laid   3.50 €/m²
                                             ───────────
                                       net    38.50 €/m²   → KB mid 39.00
                                       × 18 m² = 702.00 net
                                       × 1.19          = 835.38 gross
```

**Two independent cross-checks, both of which we can put on a slide:**

1. angebots-meister's *complete package* price for a 20 m² laminate job is
   **1 050–1 430 € gross** including skirting. Scaled to 18 m²: 945–1 287 €. Our Pos 2
   + Pos 3 = **1 052.85 €**. Inside the band, near the bottom — correct, because their
   package assumes new material throughout and ours is a repair.
2. The GDV puts the **average German `Leitungswasserschaden` at ~2 300 €**, range
   800–15 000 €. A flooring sub-invoice of 1 250 € on a single-room loss is exactly
   where it should sit.

And the geometry flag on Pos 3, which no vibes-based pipeline produces: an 18 m² room
has a perimeter of 17.0 m if square, 21.2 m at 4:1, and **24.5 m only at 6:1**. 25 lm of
skirting is therefore at the extreme tail of plausible, so `qty_factor = 0.86` and σ is
widened 20%. If R9 later shows `t` tracking the printed quantity regardless, the weight
goes to zero and we lose nothing (§7.2 risk 5).

Submission for Pos 2, with `π = 0.95 × 0.95 = 0.9025`, `σ = 0.24`:

```
median m  = 835.38
π₀        = 0.0975
b = exp(ln m + 0.24·Φ⁻¹((1/3 − 0.0975)/0.9025))  = exp(ln 835.38 + 0.24·(−0.6864)) = 708.5
a = 0.76 · m  (night, p ≈ 0)                                                       = 634.9
a = grid optimum with measured p                 (Saturday, p ≈ 0.5)             → toward c ≥ 4t
```

Note `a < b` overnight — §2.3 point 3, and the opposite of what a team that hard-coded
R6 will submit.

---

## 5. Architecture and the 24-hour build plan

### 5.1 Components and owners

```
wireclaim/
  runner.py          D1  schedule → key → decrypt → adjudicate → submit → retry → alert
  extract/           D2  pdf.py, units.py, canonical.py, test_corpus/  (30 synthetic invoices)
  kb/                D3  flooring.yaml painting.yaml plumbing.yaml electrical.yaml
                         automotive.yaml generic.yaml rates.yaml regions.yaml surcharges.yaml
  gates/             D4  coverage.py relatedness.py price.py  (async, independent, timeout-bounded)
  decide.py          D4  posterior assembly, Q⅓, R5b grid search, aggression controller
  feedback/          D5  leaderboard.py (R9 inversion), calibrate.py, store.sqlite
  dashboard/         D5  one page: next game, last submission, κ, coverage plot, missed games
  WRITEUP.md         D5  written continuously, never at the end
```

Five people, five surfaces, one interface each. The only shared contract is the
`Case` / `LineItem` dataclass (§3.1) and the gate JSON schemas (§3.3–3.5) — **write
those three files first, in the first thirty minutes, and freeze them.**

| Dev | Owns | Success measured by |
| --- | --- | --- |
| **D1 — Runner** | uptime, scheduling, submission, redundancy | games missed = **0** |
| **D2 — Extractor** | PDF → structured items, never fails | 30/30 on the synthetic corpus; 0 index misalignments |
| **D3 — Knowledge** | the KB, rate cards, build-ups, sources | `κ_R9` inside [0.85, 1.20] by game 10 |
| **D4 — Gates** | the three agents, decision rule | slow path completes < 15 s p95 |
| **D5 — Feedback + Story** | R9 inversion, calibration, dashboard, write-up | empirical coverage 75–85%; write-up done by Sun 10:30 |

### 5.2 Hour by hour

**Sat 12:00–13:00 — Hour 0: procurement, everything in parallel**
Everyone reads `README.md` §1–5 and `CONTEXT.md`. Fifteen minutes, hard stop.
- **D1** → registration desk for `TEAM_API_KEY`; case folder link; select the QuantCo
  challenge on `ehl.gg`; **install Entire on every machine — submissions are rejected
  without it, this is a hard gate and it is the only irreversible failure in the plan**;
  `brew install p7zip` ×5.
- **D2** → repo skeleton, `pixi install`, `pixi run python starter_script.py`. The
  moment the case folder lands, **case 0's `invoices.pdf` is the single most valuable
  file in the hackathon** — it is our only real sample before 15:00. Extract it, stare
  at it, diff it against the slide-5 layout in §0.
- **D3** → begins transcribing §4.2–4.6 of this document into YAML. This is *typing*,
  not research; the research is already done and sourced. ~90 minutes.
- **D4** → reads `API_HANDBOOK.md`, writes the submission payload adapter and the
  three gate JSON schemas.
- **D5** → posts the R9 calibration question in `#❓-ask-orgateam` **in the first five
  minutes**. It has the longest latency of anything we do and it gates a whole
  workstream.

**Sat 13:00–14:00 — Hour 1: the floor**
- **D1**: `runner.py` end-to-end on case 0 — poll `/leaderboard/api/games` for the
  schedule, fetch key at T−1 s, decrypt, adjudicate, POST, retry ×3.
- **D2**: extractor ladder steps 1–2 (PyMuPDF dict + `pdftotext -layout`), unit table.
- **D3**: `rates.yaml`, `flooring.yaml`, `painting.yaml` loaded and queryable.
- **D4**: **Agent C (price) only.** Coverage and relatedness can wait an hour; price is
  where the money is and it is the one that needs the KB wiring debugged.
- **D5**: SQLite schema — `games`, `items`, `submissions`, `transactions` — plus the
  leaderboard scraper skeleton.

**Sat 14:00–15:00 — Hour 2: dress rehearsal**
- Fast path green on case 0: extract → canonicalise → KB → `(a, b)` → submit.
- **Hard gate at 14:45: if the fast path is not green, D3, D4 and D5 stop everything
  and help D1 and D2.** Nothing else matters. The first game is at 15:00 and R7 says
  a missing submission is worse than a bad one.
- Stopwatch the full 60 s against case 0 three times. Record the p95.
- Ship with `a = 0.76 × median`, `b = Q₁ᐟ₃(σ_kb)`, gates off.

> **Sat 15:00 — GAME 1.** From here nothing is a big-bang deploy. Every change ships
> in the 12-minute gap between games, behind a flag, and is reverted within one game
> if the dashboard turns red.

**Sat 15:00–18:00 — games 1–14: the gates go in**
- **D1**: the double submission (T+1.5 s floor, T+10 s considered) per README #2;
  Discord alerting on a missed or failed game; **a second runner on a second machine**
  — idempotent, deterministic payload, later overwrites earlier, so redundancy is free.
- **D2**: harden against real cases as they arrive; build the 30-invoice synthetic
  corpus (multi-page, 1–12 items, decimal commas, umlaut company names, one rasterised).
- **D3**: KB expansion driven by which `TRADE` values actually appear. **Every unmatched
  description is logged with its frequency — that log is the KB backlog, in priority
  order, and it is the single best use of D3's afternoon.**
- **D4**: coverage gate live ~16:30, relatedness gate ~18:00, both behind flags.
- **D5**: R9 inversion running against the first settled games.

**Sat 18:00–21:00 — games 15–28: calibration**
- **The `κ_R9` check is the highest-value thirty seconds of the whole hackathon.** If
  it comes out near **1.19 or 0.84, we have the VAT bug** (§4.0a). Check that first,
  always, before touching anything else.
- D5's coverage plot goes on a screen everyone can see. Set σ globally so empirical
  coverage of the nominal 80% band is 75–85% (R4b).
- **D4**: images on the relatedness gate, behind a flag, and *measured* (kill criterion 3).
- **D1**: the aggression controller — estimate `p(a)` from settled transactions and
  expose it as one dial on the dashboard.

**Sat 21:00–00:00 — games 29–42: harden for the night**
- **Pipeline freeze at 23:00.** After that, config only.
- Chaos drill, all five failures, each must still produce a submission: block the LLM
  provider's domain; drop the network for 90 s; feed a corrupt PDF; feed a 0-item
  invoice; feed a 40-item invoice; feed a case with no `images.png`; feed a case with
  three images.
- Set the night profile: `p = 0`, gates on a 20 s budget with prior fallback, no deploys.
- Rota: **two awake, three asleep, swap at 04:00.** Two people, because one person
  asleep at a keyboard is the same as zero.

**Sun 00:00–08:00 — games 43–80: the harvest (~38 games while the field sleeps)**
- The awake pair watches and does nothing else. **No deploys 00:00–06:00 unless a game
  is being missed.** This is the period the README identifies as decisive; the way to
  win it is to be boring.
- Automated, every 12 min 37 s: settlement → R9 inversion → `κ` update → next game uses
  it. That is the compounding, and it needs no human.
- Whoever is awake keeps writing `WRITEUP.md` — each κ shift, each calibration plot,
  each surprise, timestamped. **The write-up is a log, not an essay.**

**Sun 08:00–10:30 — games 81–93: the last exploit window**
- The field wakes up and recalibrates. If teams set `b` defensively high after a night
  of wrongful rejections, `p(a)` spikes and R5's free option reopens — the controller
  should find it on its own. **Watch it, do not override it.**
- **D3**: final pass on the top unmatched items from the overnight log.

**Sun 10:30–12:00 — land it**
- **10:30 code freeze. Full stop.** Only the runner runs.
- **D5 + D1**: finalise the write-up (it has been written all night), export the
  calibration plots, **submit on `ehl.gg` by 11:45 — not 11:59.**
- **D2 + D3 + D4**: build the five-minute pitch. Live dashboard; the §4.7 worked case
  end to end; the σ-versus-income table from §2.3; the calibration plot; the
  uncovered-item corollary (§2.4) as the closer.
- 11:50 last game — watch it land. 12:00 deadline. 12:30 pitch.

---

## 6. Latency budget — how this survives 60 seconds

### 6.1 The answer in one sentence

**A submission is on file at T+1.6 s, before any model has been called.** Everything
described in §3 is an *overwrite*, and the rules say later submissions overwrite
earlier ones. The elaborate pipeline therefore cannot cost us a game; it can only fail
to improve one.

### 6.2 The timeline

| Phase | p50 | p95 | On timeout |
| --- | --- | --- | --- |
| T−2 s: warm HTTP pool, KB already resident, pre-open LLM client | — | — | — |
| Key fetch (poll every 150 ms from T−1 s) | 0.15 s | 0.6 s | retry to T+20 s, then alert |
| Download + decrypt (`7z -y -p…`, `timeout=5`) | 0.20 s | 0.5 s | fall back to in-process `py7zr` |
| Read `policy.txt`, `description.txt` (UTF-8, `errors=replace`) | 0.01 s | 0.03 s | — |
| PDF extract, ladder step 1 (PyMuPDF `get_text("dict")`) | 0.09 s | 0.20 s | step 2 → 3 → 4 |
| Normalise units + canonicalise (alias table + rapidfuzz) | 0.01 s | 0.02 s | generic trade fallback |
| KB lookup + posterior with π = 1 + `(a,b)` | <0.01 s | <0.01 s | — |
| **SUBMIT #1 — the floor** | **T+1.1 s** | **T+1.9 s** | retry 0.2/0.5/1/2 s |
| ↓ *(gates launched at T+1.0 s, in parallel, not waiting for submit #1)* | | | |
| Coverage gate (short doc, small fast model) | 3 s | 6 s | drop, `p_covered = 0.8` |
| Relatedness gate, text only | 3 s | 6 s | drop, `p_related = 0.9` |
| Relatedness gate, **with image** (vision) | 6 s | 11 s | drop, text verdict stands |
| Price gate (structured, bounded output) | 4 s | 8 s | drop, `factor = 1.0` |
| Posterior assembly + R5b grid (200 points) | <0.01 s | <0.01 s | — |
| **SUBMIT #2 — considered** | **T+8 s** | **T+14 s** | — |
| Hard cut: any gate still open is dropped | T+35 s | | |
| **SUBMIT #3** — only if a late gate landed in (35, 48] s | T+48 s | | |
| Absolute stop. Nothing sent after this. | T+52 s | | |

Total LLM spend: ~4 calls × 100 games ≈ 400 calls, of which ~100 are vision. Trivial.

### 6.3 The degradation ladder, in the order things actually break

1. **LLM provider is down or rate-limits.** Submit #1 already went. Nothing happens.
   *This is the entire reason for the fast path and it will earn its keep at least
   once during the night.*
2. **One gate times out.** Its prior is used unchanged. A missing gate is a missing
   *update*, not a failure — which is precisely why the gates are independent and
   why we did not build one big prompt.
3. **PDF extract yields zero rows.** Ladder steps 2 and 3, then: count rows matching
   `^\s*\d+\s` to recover *the item count* even from a mangled parse, and price every
   item at the trade-level default band. An indexed guess beats no submission by a
   very large margin (R7).
4. **7z fails.** Second, independent in-process decryptor. Never let a subprocess that
   can block on a password prompt sit on the critical path without a timeout.
5. **Our POST fails.** Exponential backoff to T+55 s, then the second runner's copy
   lands anyway.
6. **The whole machine dies.** Second runner on a second machine, different network.
   Deterministic payload ⇒ idempotent ⇒ redundancy costs nothing.

### 6.4 The guard that stops the slow path making things worse

> **Submit #2 replaces submit #1 only if every returned gate parsed as valid JSON and
> the resulting `a` lies within ×[0.3, 3.0] of the fast-path `a`.** Outside that band,
> keep the floor and log loudly.

An elaborate pipeline's real risk is not that it is slow — it is that it is
*confidently wrong* in a way the simple path was not. This one line makes the slow
path strictly non-decreasing in quality, which is what licenses building it at all.

### 6.5 On images specifically

Given F5 — the sample photo is a stock image that does not even match the invoiced
room — the vision call buys us: peril category, room type, and a coarse
cosmetic-versus-structural read. That is worth roughly ±20% on the price band and a
modest bump to `π_rel`. It costs 6–11 s of a 60 s budget.

Verdict: **run it, but only on the third parallel slot, and only until kill criterion
3 at Sat 22:00 says whether it earns its latency.** Expectation going in: it does not,
and we drop it. Build it anyway, because measuring it and *reporting that we dropped
it* is worth more in the write-up than a feature we never tested.

---

## 7. Kill criteria and honest downside

### 7.1 Kill criteria — each with a time, a metric, a threshold, an action

| # | When | Metric | Threshold | Action |
| --- | --- | --- | --- | --- |
| 1 | Sat 16:30 (~7 settled games) | `κ = median(t̂ / R9 bracket midpoint)` | `κ ≈ 1.19` or `≈ 0.84` | **VAT bug.** One line. Check this before anything else, every time. |
| 1b | same | same | `κ ∉ [0.85, 1.20]` | Demote KB from authority to prior: scale all `net_unit_mid` by `κ`, widen σ to 0.45 |
| 1c | same | same | `κ ∉ [0.5, 2.0]` | The generator is not pricing the German market. Go to §7.2 risk 1. |
| 2 | Sat 18:00 | share of items marked `NOT_COVERED` | > 40% | Gate is hallucinating exclusions → cap `π₀` at 0.35 so coverage can never alone zero `b` |
| 2b | Sat 18:00 | same | < 3% | Gate is asleep → confirm `policy.txt` actually reaches the prompt |
| 3 | Sat 22:00 | Δ`t̂` from the image branch, and whether it improves R9 agreement | <5% change, or no improvement | **Drop images.** Reclaim 6–11 s and the vision spend. |
| 4 | Sat 22:00, then hourly | empirical coverage of the nominal 80% interval | <65% → widen σ; >92% → narrow σ | One scalar. This is R4b and it is the only legitimate way to set interval width. |
| 5 | Sun 02:00 | games missed in the last 6 h | any | Night rota failed. The awake pair stops all other work until it is zero. |
| 6 | every game | `|a₂ / a₁|` | outside ×[0.3, 3.0] | Do not send submit #2. Keep the floor. |
| 7 | Sat 20:00 (~24 settled games) | measured per-item σ against R9 brackets | > 0.6 | **The grounding is not buying what §2.3 promises.** Move D3 and D4 onto the R9 loop; the pipeline is unchanged, only the effort moves. |

### 7.2 Honest downside

**Risk 1 — and it is the real one: `t` is synthetic, and it is probably a model's
opinion rather than the market's.** QuantCo generated 100 cases; they almost certainly
generated `t` alongside them, most plausibly by asking a model to price each line item,
perhaps with a human pass. If so, the target is not the German market — it is *a
model's belief about the German market*. Two consequences:

- Our expert build-up could be systematically biased against it. This is the *cheap*
  failure: a constant bias is one multiplication, `κ_R9` catches it by game 5, and the
  fix is kill criterion 1b. We lose the first handful of games and nothing else.
- The dispersion we should be modelling is the *generator's* noise, not the market's.
  If the generator itself is noisy, no amount of domain grounding pushes σ below that
  floor. If R4b says our true σ cannot go below ~0.45, the §2.3 table says we capture
  ~48% of attainable income rather than ~64%. **Still ahead of a team at σ ≈ 1.0
  (31%), but the headline number shrinks by half.** We should put this in the write-up
  ourselves rather than let QuantCo find it — it is a better story with the caveat than
  without.

**Risk 2 — the field converges.** If many teams also land near `t`, everyone's `b` sits
near `t`, `p(a)` collapses, and the tournament is decided purely by fair-zone accuracy.
Note that this is a risk to R5's *free-option arm*, not to this plan — it makes §2.3's
lever the only lever, which is the game we want to be playing.

**Risk 3 — elaboration eats the team.** Three gates, a KB, a runner, a calibration loop
and a dashboard is a lot for five people in 24 hours, and the failure mode is a
half-finished everything at 03:00. The mitigation is structural rather than optimistic:
the 14:45 hard gate; the fact that every component after the fast path is independently
droppable; and the honest observation that **if we ship only the extractor, the KB and
the fast path, we still have a better `t̂` than the field.** The KB alone is a winning
artefact. Everything else is upside, and can be cut at any hour without rework.

**Risk 4 — the KB does not cover the trades that appear.** We seed Flooring, Painting,
Plumbing/SHK, Electrical, Automotive, Drywall and Screed. If a third of cases turn out
to be roofing, glazing or landscaping, those fall to the generic fallback at σ = 0.55
and we are merely at the field's accuracy on them. Mitigations: the trade-level rate
card (§4.2) covers 14 trades and is never absent; the unmatched-description log is
worked continuously; and adding a KB row is a YAML edit that ships between games.

**Risk 5 — the quantity-plausibility check is speculative.** §3.4 is honest about
this: because `QTY` is printed for everyone, the generator may well define
`t = qty × fair_unit_price` and never inflate quantities at all. It ships at weight
0.3 and R9 decides. If the brackets show `t` tracking printed quantity even on absurd
quantities, the weight goes to 0 and we lose nothing but a nice slide.

**What would make us abandon this plan.** Kill criterion 7: if by Sat 20:00 our measured
per-item σ is no better than 0.6, domain grounding is not doing what §2.3 promises, and
the leaderboard should be the only teacher. Even then, **the pipeline does not change** —
the KB simply becomes a weak prior that R9 overwrites, and D3's afternoon becomes D5's
evening. There is no version of this plan that has to be thrown away, which is the main
reason to bet on it.

---

## 8. What this plan is *not*

It is not the whole entry. It says nothing about uptime engineering, the R5 aggression
controller's `p(a)` estimator, or the leaderboard scraper — those are strong, separable
workstreams and other pitches in `docs/strat-*/` should own them. **This plan owns
exactly one thing: the number in the middle.** Every other strategy in this repo takes
`t̂` as an input. This is the one that builds it, and the §2.3 table is the argument
that it is worth five people's attention for one afternoon.
