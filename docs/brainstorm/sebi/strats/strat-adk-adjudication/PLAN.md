# Strategy: **The ADK Adjudication Layer**

> The realisation of [ADR 0001](../../adr/0001-the-model-reads-the-engine-prices.md) —
> _the model reads, the engine prices_ — as a concrete Google ADK agent team, an
> evidence contract, and a workflow graph.
>
> This is **not** a competing pitch. ADR 0001 is Accepted; this document is its
> wiring. It assumes `README.md` (R1–R10) and `CONTEXT.md` as read, and it builds
> **on** [`strat-adjuster`](../strat-adjuster/PLAN.md) (the three gates, the German
> trade Price Memory, the extraction ladder, the latency ladder) and
> [`strat-quant`](../strat-quant/PLAN.md) (three-point elicitation, disagreement as
> width, censored-likelihood calibration). Where those two disagree, this document
> says so and picks.
>
> House patterns are lifted from SampleRepo's
> `server/app/services/ai/{agents,runtime,cached_call}.py` and its ADR 0021 / ADR
> 0028 — the ancestors of our ADR 0001 and of §4 respectively.

---

## 1. The principle, and why ADR 0001 forces it

**Agents read. The engine prices.** Nothing else in this document is negotiable
against that sentence.

ADR 0001 gives four reasons; each one lands somewhere specific in this design, and
it is worth naming the landing site because that is what makes the wiring
inevitable rather than stylistic:

| ADR 0001 pressure                                                                  | Where it lands here                                                                                                                                             |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The pricing rules are arithmetic" (R5b ≈ 0.7 · t̂, R6 bottom third, R6b shrinkage) | §7 — every one of those lives in `decide.py`, and **no agent has a field to express them in**                                                                   |
| "What we need is a distribution, not a number" (R4b)                               | §3.3 — the evidence contract carries a **band and named anchors**, and the _disagreement between the anchor build-up and the market band_ is where σ comes from |
| "Coverage is worth more than pricing" (`t = 0`)                                    | §2.3, §3.4 — the coverage gate is the only one sampled twice, and its confidence becomes a **spike at zero**, never a boolean                                   |
| "Retrieved prices must not launder into verdicts"                                  | §5.4 — a set-membership check on `memory_key`, not a trust exercise                                                                                             |

The structural expression of the decision is one line, and it is the single most
important line in the whole design:

> **No Pydantic class in `evidence.py` has a field for a Charge, a Limit, or a Fair
> Value.** An agent that wanted to emit one has nowhere to put it.

This is exactly the move SampleRepo's ADR 0021 made — the engine owns the
verdict, the model owns the explanation — with the stakes raised, because there the
unanchored artefact was _a word on a card_ and here it is the number we are paid on,
a hundred times, unattended, through the night.

A second, weaker principle follows from it and saves a lot of argument later:

> **The evidence module imports nothing from `google.adk`.** `evidence.py` and
> `assemble.py` are plain Pydantic + stdlib. The engine, the tests, the backtest and
> the Fast Path can all read and construct evidence with no provider, no API key and
> no network. Only `agents.py`, `graph.py` and `runtime.py` know ADK exists.

That is what makes §5's determinism test possible at all, and it is what makes §6's
provider question a _config_ question rather than a rewrite.

### 1.1 Module layout

```
src/wireclaim/
  adk/
    models.py      # the provider seam — the ONLY place a model id appears
    prompts.py     # shared instruction constants + prompt-version constants
    agents.py      # LlmAgent factories (SampleRepo agents.py shape)
    graph.py       # the Workflow: START -> gates -> JoinNode
    runtime.py     # runner/session driving (SampleRepo runtime.py shape)
  evidence.py      # THE CONTRACT. Pydantic. No adk import. No Charge/Limit/Fair Value.
  assemble.py      # evidence -> Posterior. Deterministic. No adk import.
  decide.py        # Posterior -> Submission (R5b/R6/R5c). Deterministic. No adk import.
  memory.py        # Price Memory: retrieval, injection, and the anti-laundering guard
```

Import direction is one-way and enforced by a lint rule (`adk` may import
`evidence`; `evidence` may not import `adk`). One rule, one test, and it is the
whole architecture.

---

## 2. The agent team

### 2.0 Model tiers under a 60-second budget — and why the price gate is _three cheap calls_, not one expensive one

The Slow Path opens at T+1.0 s (after the Fast Path Submission is already on file)
and is hard-cut at T+35 s (`strat-adjuster` §6.2). That is ~30 s of wall clock for
everything in this document, and the gates run in parallel, so the budget per gate
is one gate's latency, not their sum.

Three tiers, named once, resolved in `models.py`:

| Tier        | Used by                   | Why                                                                   |
| ----------- | ------------------------- | --------------------------------------------------------------------- |
| `FAST`      | relatedness, image        | Classification against a short text/photo. Latency dominates value.   |
| `REASONING` | coverage, price framings  | Reading comprehension against a policy document; anchor construction. |
| `VISION`    | image, extractor fallback | Must accept `inline_data`.                                            |

The one genuinely contested call is the price gate, and the answer is **not** the
obvious one:

> **Three `REASONING`-tier calls at temperature 0 under three different framings,
> in parallel, beat one Pro-tier call — because R4b says the quantity that
> determines our score is the posterior's _width_, and one call of any size returns
> a point and a fabricated interval.**

A single deep call gives a better centre. Three deliberately different framings give
a centre _and_ a measured dispersion (`strat-quant` layer 3: between-framing variance
is a far better proxy for epistemic error than any self-report). ADR 0001's own
"Consequences" names the failure this defends against — _"a model that fabricates a
confident narrow band poisons the posterior just as surely as one that fabricates a
price"_ — and disagreement is the only defence that does not require the model to be
honest about itself. It is also faster: three 5-second calls in parallel finish in
5 seconds; one 25-second reasoning call risks the hard cut.

Coverage is sampled **twice**, for the same reason and a sharper one: π₀ is the only
evidence quantity that can drive the Limit to exactly zero (§3.4), so its width
matters more than its centre, and two disagreeing coverage reads are a signal we
must not throw away. Cost: two short calls over a short document. Trivial.

Relatedness and image are sampled once. They move π_rel and the band by at most
±20 % (`strat-adjuster` §6.5); a second sample would not pay for its latency slot.

**Total: 7 model calls per Case (6 without images), all parallel, ~6 s p50 / ~12 s
p95 wall.** Against ~100 Games that is ~700 calls. Trivial spend, and the entire
elaboration is an _overwrite_ of a Submission already on file.

### 2.1 The provider seam and the shared constants

```python
# src/wireclaim/adk/models.py
"""The provider seam. The ONLY module in the repo that names a model.

Every agent factory asks for a TIER, never for a model id. Switching provider
(§6) is a change to `_RESOLVE` and nothing else — no factory, no prompt, no
schema and no test moves.
"""
from __future__ import annotations

from enum import StrEnum

from google.adk.models.base_llm import BaseLlm

from wireclaim.config import settings


class Tier(StrEnum):
    FAST = "fast"
    REASONING = "reasoning"
    VISION = "vision"


def resolve(tier: Tier) -> str | BaseLlm:
    """Return whatever ``LlmAgent.model`` accepts for this tier.

    A bare string is enough on both providers we care about: ADK's LLMRegistry
    resolves ``gemini-*`` to ``Gemini`` and ``gpt-*`` / ``o<N>-*`` to
    ``google.adk.labs.openai.OpenAILlm`` (verified against google-adk 2.7.1,
    ``models/__init__.py:_LAZY_PROVIDERS``). We return ``str | BaseLlm`` anyway
    so that a pre-configured client (a proxy base_url, a tighter httpx timeout,
    an org header) can be substituted here without touching a factory.
    """
    return {
        Tier.FAST: settings.MODEL_FAST,
        Tier.REASONING: settings.MODEL_REASONING,
        Tier.VISION: settings.MODEL_VISION,
    }[tier]
```

```python
# src/wireclaim/adk/prompts.py
"""Shared instruction constants and prompt-version constants.

Two rules, both borrowed from SampleRepo's agents.py and both load-bearing
here for a reason that module did not have: our prompts are inputs to a
*calibration fit* (R9), not just to prose.

1. A constant appended to several instructions is versioned by bumping EVERY
   version constant that carries it. SampleRepo bumped three at once when
   PROSE_CONTRACT changed; we do the same, because a settled Game calibrated
   under prompt "cov-3" is not evidence about prompt "cov-4".
2. Every version constant is copied into the evidence packet and into the
   Price Memory row. `strat-quant` §3.2 fits (beta, gamma, delta) on censored
   labels; fitting across a prompt change is fitting on two different
   instruments.
"""

# --- version constants: bump on ANY change to the instruction they name ------
EXTRACT_PROMPT_VERSION = "ext-1"
COVERAGE_PROMPT_VERSION = "cov-1"
RELATEDNESS_PROMPT_VERSION = "rel-1"
PRICE_PROMPT_VERSION = "pri-1"
IMAGE_PROMPT_VERSION = "img-1"

# Bump every version above when this changes — it is appended to all of them.
EVIDENCE_CONTRACT = (
    "YOU DO NOT PRICE THE CLAIM. You are one half of a two-part system: you "
    "read, and a separate deterministic engine decides. NEVER state, imply or "
    "hint at what should be charged, what should be paid, what is 'fair', or "
    "what the claim is 'worth'. Your output schema has no field for any of "
    "those and inventing one is a hard failure. "
    "EVIDENCE ONLY: every judgement you return must be traceable to text you "
    "were given. Where the schema asks for a verbatim quote, paste the source "
    "characters exactly — do not paraphrase, do not translate, do not tidy. If "
    "the source does not address the question, say so with the schema's "
    "designated 'unstated' value; NEVER invent a clause, a sentence or a "
    "source that is not in front of you. "
    "CALIBRATION: where you give a low/high range, it is an 80% interval — you "
    "should expect the truth to fall OUTSIDE it about one time in five. A range "
    "that is never wrong is a range that is useless to us."
)

# Appended to the two gates that must be reluctant to say NO (see 2.3, 2.4).
RELUCTANCE = (
    "You are deliberately RELUCTANT to return a negative verdict. A wrongly "
    "negative verdict is roughly eight times more expensive to us than a "
    "wrongly positive one. When the source is silent, return the 'unstated' "
    "verdict with a moderate probability — silence is not exclusion."
)

# Appended to the price framings only. The Price Memory never reaches the
# coverage or relatedness prompts at all (see 5.4) — a different assembler
# builds those, so this is structural, not a matter of discipline.
ANCHOR_CONTRACT = (
    "ANCHORS ARE NOT DECORATION. The named anchors you return are a SECOND, "
    "INDEPENDENT estimate: the engine reconciles your anchor build-up "
    "(material + hourly_rate x time_per_unit) against your market band, and "
    "the DISAGREEMENT between them sets how much the engine trusts you. A "
    "build-up that has been reverse-engineered from your band to make the two "
    "agree destroys the only calibration signal you produce. Build the anchors "
    "from what you know about the trade, state the band from what you know "
    "about the market, and let them disagree if they disagree. "
    "NET, ALWAYS. Every figure you return is NET of VAT, per single unit of "
    "the stated unit of measure. The engine applies quantity and VAT. If your "
    "source knowledge is a consumer-facing gross price, divide it by 1.19 "
    "before returning it and say so in `basis_note`. "
    "PROVENANCE: any anchor you took from the RETRIEVED PRIOR block must be "
    "returned with provenance PRICE_MEMORY and that block's exact memory_key. "
    "Any anchor you produced yourself must be MODEL_JUDGEMENT. Copying a "
    "retrieved number and labelling it MODEL_JUDGEMENT is a hard failure."
)
```

### 2.2 Agent 1 — the invoice extractor (`VISION`, fallback rung only)

The extractor is **not** on the normal path. `strat-adjuster` §3.1 owns extraction
as a deterministic ladder (PyMuPDF word boxes → `pdftotext -layout` → pdfplumber),
and that ladder also feeds the Fast Path, which fires before any agent exists. The
agent is rung 4: it runs only when rungs 1–3 return zero rows, or when
`len(items) != max_pos` (the index-misalignment assertion).

This placement is the whole point. Index alignment is the failure that shifts every
Charge and Limit by one position and costs the entire Game; the model is the _last_
thing we want owning it, and it earns its slot only where the alternative is nothing.

```python
class ExtractedLineItem(BaseModel):
    """One row of the Invoice as printed. NO PRICES — the invoice has none."""
    index: int = Field(description="0-based position in the printed LINE ITEMS block")
    pos: str = Field(description="the POS. cell verbatim: '1', '2.1', '3a'")
    description: str = Field(description="the DESCRIPTION cell verbatim, no tidying")
    qty_text: str = Field(description="the QTY cell verbatim, e.g. '18' or '18,5'")
    unit_text: str = Field(description="the UNIT cell verbatim, e.g. 'm2', 'lm', 'AW'")


class ExtractedInvoice(BaseModel):
    trade: str | None = Field(description="the TRADE header field, verbatim, else null")
    issuer_name: str | None
    invoice_no: str | None
    items: list[ExtractedLineItem]
    excluded_rows: list[str] = Field(
        description="rows you judged NOT to be Line Items (Net / plus VAT / Total "
                    "amount / Zwischensumme / MwSt / Summe), verbatim, so the "
                    "engine can audit your row count"
    )
    prompt_version: str


def invoice_extractor() -> LlmAgent:
    """Rasterised-PDF fallback. Runs ONLY when the deterministic ladder fails.

    Vision tier because by the time we are here the PDF has no usable text layer.
    `excluded_rows` is not diagnostics: it is the audit that lets the engine
    assert `len(items) + len(excluded_rows)` covers every printed row, which is
    the check that catches the one failure that costs a whole Game.
    """
    return LlmAgent(
        name="invoice_extractor",
        model=resolve(Tier.VISION),
        instruction=(
            "You are reading a German tradesman's invoice rendered as an image. "
            "Transcribe the LINE ITEMS table EXACTLY as printed, one object per "
            "printed row, in printed order, 0-indexed.\n"
            "The UNIT PRICE, VAT and TOTAL columns are BLANK BY DESIGN. Do not "
            "fill them, do not estimate them, do not mention them.\n"
            "Rows reading Net / plus VAT / Total amount / Zwischensumme / MwSt / "
            "Summe are footer arithmetic, NOT Line Items: put them verbatim in "
            "`excluded_rows`. A page header repeated mid-document is also not a "
            "Line Item.\n"
            "Copy QTY and UNIT as printed characters, including a decimal comma "
            "('18,5') and superscripts ('m2' for a squared metre). The engine "
            "normalises them; your job is fidelity, not interpretation.\n"
            + EVIDENCE_CONTRACT
        ),
        output_schema=ExtractedInvoice,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=DETERMINISTIC,
    )
```

### 2.3 Agent 2 — coverage (`REASONING`, sampled twice)

Reads: the Policy, the Line Item list, the trade. **Does not read** the Damage
Description, the Price Memory, the knowledge base, or any price. It cannot
rationalise a number because it has never seen one.

Two instances with different framings — `coverage_agent("strict")` reads the policy
as an underwriter listing what is _in_; `coverage_agent("charitable")` reads it as a
claims handler asking what would have to be true for this to be _out_. Same schema,
same temperature, different question. Their disagreement is π₀'s width.

```python
def coverage_agent(framing: Literal["strict", "charitable"]) -> LlmAgent:
    return LlmAgent(
        name=f"coverage_{framing}",
        model=resolve(Tier.REASONING),
        instruction=(
            "You are a German P&C claims adjuster performing a "
            "DECKUNGSPRUEFUNG. You are given an insurance Policy and the Line "
            "Items of an Invoice. For EACH Line Item decide whether this Policy "
            "covers this specific work.\n\n"
            + _FRAMING[framing] + "\n\n"
            "A German policy typically covers the CONSEQUENCES of the insured "
            "peril but excludes: the cause itself where the policy says so; "
            "wear and maintenance (Verschleiss, Wartung); gradual damage "
            "(allmaehliche Einwirkung); pre-existing defects (Baumaengel); "
            "betterment beyond restoration (Neu fuer Alt, upgrades); anything "
            "outside the insured location; and perils needing a rider the "
            "policy does not name (Elementarschaeden, Rueckstau, Grundwasser).\n"
            "QUOTE THE CLAUSE. `clause_verbatim` must be characters copied from "
            "the Policy. If no clause addresses this item, return verdict "
            "UNSTATED and clause_verbatim null. An invented exclusion is the "
            "most expensive mistake you can make here.\n"
            "Record a deductible or sub-limit if the policy states one. Do NOT "
            "apply it to anything — recording is your whole job.\n"
            + RELUCTANCE + " " + EVIDENCE_CONTRACT
        ),
        output_schema=CoverageReport,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=DETERMINISTIC,
    )
```

The verbatim-quote requirement is the anti-hallucination mechanism, and it is not a
style preference: a model that must paste the sentence invents far less than one
that need only assert. The engine then **verifies the paste** (§3.2) — a quote that
is not a substring of the Policy is dropped and the verdict is demoted to
`UNSTATED`. That check is four lines of Python and it converts "we asked it to
quote" into "it quoted".

### 2.4 Agent 3 — relatedness (`FAST`)

Reads: the Damage Description, the Line Item list. **Does not read** the Policy or
any price. Image findings arrive separately (§2.6) and are fused by the engine, not
by this agent — so a stock photograph that does not match the Case (`strat-adjuster`
F5) cannot silently overturn a text verdict.

```python
def relatedness_agent() -> LlmAgent:
    return LlmAgent(
        name="relatedness",
        model=resolve(Tier.FAST),
        instruction=(
            "You are checking KAUSALITAET UND PLAUSIBILITAET. Given a Damage "
            "Description and the Line Items of an Invoice, decide for each Line "
            "Item whether the work is plausibly caused by, and proportionate "
            "to, the described damage.\n"
            "RELATED — the work follows from the described damage.\n"
            "UNRELATED — the item belongs to a different room, a different "
            "peril, or a different trade than the description supports.\n"
            "SCOPE_EXCESSIVE — related, but the stated quantity or "
            "specification exceeds what the description implies: a whole-flat "
            "quantity for a single-room loss, premium material where the loss "
            "was standard, work on undamaged parts.\n"
            "Quote the sentence you relied on, verbatim, in "
            "`evidence_verbatim`.\n"
            "`qty_expected_lo/hi` is an 80% interval on the quantity the "
            "DESCRIPTION implies, in the item's own unit — null when the "
            "description implies nothing about quantity, which is common and "
            "not a failure. Do NOT do geometry: if the description gives an "
            "area and the item is in linear metres, return null and let the "
            "engine compute the perimeter.\n"
            + RELUCTANCE + " " + EVIDENCE_CONTRACT
        ),
        output_schema=RelatednessReport,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=DETERMINISTIC,
    )
```

Note the explicit "do NOT do geometry". `strat-adjuster` §3.4's perimeter table is
deterministic arithmetic and belongs in `assemble.py` (§7). Asking the model to do
it is asking it to be worse at it, slower, and unauditable.

### 2.5 Agent 4 — price evidence (`REASONING`, three framings)

Reads: the Line Item text, the extracted quantity and unit, the trade, and — fenced,
labelled and only here — the retrieved Price Memory block. **Does not read** the
Policy or the Damage Description: coverage and relatedness are not its job, and a
price framing that decides "not covered" and returns a zero poisons the mixture
(`strat-quant` §3.1, "one rule that matters").

Every framing prices the item **conditional on it being covered and related**. The
prompt says so explicitly. π₀ is applied once, by the engine, at the end.

The three framings, deliberately different estimators:

| id                  | framing                                                    | why it is a different estimator                         |
| ------------------- | ---------------------------------------------------------- | ------------------------------------------------------- |
| `sachverstaendiger` | court-appointed expert, "maximum defensible net unit rate" | closest to the literal definition of Fair Value         |
| `kalkulator`        | the tradesman writing this invoice                         | anchors on market billing convention, not defensibility |
| `einkaeufer`        | procurement analyst: wholesale material + tariff labour    | bottom-up; ignores billing convention entirely          |

```python
def price_evidence_agent(framing: Framing) -> LlmAgent:
    """One price framing. Emits a BAND and NAMED ANCHORS. Never a price.

    'Never a price' is enforced by the schema, not by the prompt: `PriceReport`
    has no total, no gross, and no quantity-multiplied field. The engine owns
    quantity x unit rate x VAT (see 7).
    """
    return LlmAgent(
        name=f"price_{framing}",
        model=resolve(Tier.REASONING),
        instruction=(
            _PRICE_FRAMING[framing] + "\n\n"
            "For each Line Item return, NET and PER SINGLE UNIT of the stated "
            "unit of measure:\n"
            "  * `net_unit_lo/mid/hi` — an 80% interval on the net unit rate.\n"
            "  * `anchors` — the NAMED components you built that view from. At "
            "minimum a TRADE anchor (which German trade does this work), and "
            "wherever the work has a labour content: HOURLY_RATE (net "
            "Stundenverrechnungssatz for that trade, EUR/h) and TIME_PER_UNIT "
            "(Zeitansatz, hours per single unit). Wherever it has a material "
            "content: MATERIAL (net EUR per single unit). Add DISPOSAL, "
            "CALLOUT or MARKET_UNIT_RATE anchors when they apply.\n"
            "  * `deviation_factor` — if a REFERENCE BAND was supplied for this "
            "item, the multiplier on it this specific wording justifies, in "
            "[0.6, 1.6]; 1.0 when the wording justifies nothing. Reasons to go "
            "up: explicit premium specification, difficult access, small "
            "quantity, emergency or out-of-hours wording, contaminated or "
            "hazardous material, water-swollen material. Reasons to go down: "
            "partial scope, basic specification, large quantity, work already "
            "implied by another Line Item on this same Invoice. Name the driver "
            "in `deviation_reason`.\n"
            "  * `overlaps_index` — the index of another Line Item on this "
            "Invoice whose scope already contains this one (Doppelabrechnung), "
            "or null.\n\n"
            "PRICE AS IF COVERED AND RELATED. Whether the Policy covers this "
            "and whether it follows from the damage are decided elsewhere by "
            "other readers. If you believe an item is not covered, price it "
            "anyway, exactly as if it were. Returning a zero or a token amount "
            "because you doubt coverage corrupts a calculation you cannot see.\n"
            + ANCHOR_CONTRACT + " " + EVIDENCE_CONTRACT
        ),
        output_schema=PriceReport,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=DETERMINISTIC,
    )
```

### 2.6 Agent 5 — image (`VISION`, only when `images.png` exists)

`strat-adjuster` F5 established that the sample photograph is a stock image that did
not even match the invoiced room. The design consequence is absolute and it is
encoded in the schema, not in the prompt: **`ImageReport` has no numeric field.** No
area, no count, no measurement. A photograph cannot tell you 18 m² from 30 m², and a
schema that cannot express a measurement cannot be talked into one.

```python
def image_agent() -> LlmAgent:
    return LlmAgent(
        name="image",
        model=resolve(Tier.VISION),
        instruction=(
            "You are given one or more photographs attached to a claim, and the "
            "Damage Description. Answer THREE categorical questions and nothing "
            "else.\n"
            "1. `peril_depicted` — WATER, FIRE, IMPACT, VEHICLE, STORM, "
            "BURGLARY, OTHER, or INDETERMINATE.\n"
            "2. `room_type` — the room or location depicted, one or two words, "
            "or null.\n"
            "3. `severity` — COSMETIC (staining, a single surface) or "
            "STRUCTURAL (structure exposed, screed visible, ceiling down) or "
            "INDETERMINATE.\n"
            "Then `matches_description`: does the photograph depict the SAME "
            "event the Damage Description describes? A stock or illustrative "
            "photograph that shows a different room or a different peril is "
            "NORMAL in this dataset and is not evidence of anything — say "
            "false with a high `mismatch_confidence` and move on.\n"
            "MEASURE NOTHING. Do not estimate an area, a length, a count, a "
            "cost or a duration from a photograph. Your schema has no field "
            "for any of them.\n"
            + EVIDENCE_CONTRACT
        ),
        output_schema=ImageReport,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=DETERMINISTIC,
    )
```

The engine uses `ImageReport` in exactly two places (§3.3): it nudges π_rel, and
`severity` shifts the band by at most ±20 %. When `matches_description` is false, it
does neither — it only widens σ slightly, because a photograph we cannot trust is
uncertainty, not information.

---

## 3. The evidence contract

This is the most important artefact in the document. Everything upstream produces
it; everything downstream consumes it; and it is what makes the ADR's claim —
_identical evidence yields an identical Submission, and that is assertable in a
test_ — true rather than aspirational.

### 3.1 The schemas

```python
# src/wireclaim/evidence.py
"""The evidence contract between the ADK agent team and the pricing engine.

ADR 0001: agents read, the engine prices. This module is where that decision
is made structural — there is NO field here for a Charge, a Limit or a Fair
Value, so no agent can emit one, whatever a prompt says.

Imports nothing from google.adk, deliberately. The engine, the tests, the
backtest and the Fast Path construct and read evidence with no provider
configured and no network.

OpenAI strict structured outputs (see 6) forces two authoring rules on every
model below:
  * EVERY field is required in the wire schema, whatever its Python default —
    `enforce_strict_openai_schema` sets `required = sorted(properties)`. So an
    optional field is declared `X | None`, never omitted, and the prompt is
    told to emit null.
  * Numeric bounds live in `field_validator`, NOT in `Field(ge=..., le=...)`.
    Constraint keywords in the JSON Schema are the sharpest edge in strict
    mode; validating in Python costs nothing and cannot 400 at T+8s.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


# --- vocabulary (CONTEXT.md) --------------------------------------------------

class Unit(StrEnum):
    SQM = "SQM"; LM = "LM"; EACH = "EACH"; HOUR = "HOUR"; DAY = "DAY"
    KG = "KG"; M3 = "M3"; FLAT = "FLAT"; AW = "AW"; PCT = "PCT"; UNKNOWN = "UNKNOWN"


class Provenance(StrEnum):
    """Where a figure came from. The engine treats these DIFFERENTLY (5.4)."""
    READ_FROM_CASE = "READ_FROM_CASE"      # copied from the Case's own documents
    KB_PRIOR = "KB_PRIOR"                  # our seeded German trade rate card
    PRICE_MEMORY = "PRICE_MEMORY"          # recovered from a settled Game (R9)
    MODEL_JUDGEMENT = "MODEL_JUDGEMENT"    # the agent's own domain knowledge


class CoverageVerdict(StrEnum):
    COVERED = "COVERED"
    NOT_COVERED = "NOT_COVERED"
    UNSTATED = "UNSTATED"


class RelatednessVerdict(StrEnum):
    RELATED = "RELATED"
    UNRELATED = "UNRELATED"
    SCOPE_EXCESSIVE = "SCOPE_EXCESSIVE"


class AnchorKind(StrEnum):
    TRADE = "TRADE"                        # which German trade; carries no number
    HOURLY_RATE = "HOURLY_RATE"            # net EUR/h, Stundenverrechnungssatz
    TIME_PER_UNIT = "TIME_PER_UNIT"        # hours per single unit, Zeitansatz
    MATERIAL = "MATERIAL"                  # net EUR per single unit
    MARKET_UNIT_RATE = "MARKET_UNIT_RATE"  # net EUR per single unit, all-in
    DISPOSAL = "DISPOSAL"
    CALLOUT = "CALLOUT"


# --- coverage -----------------------------------------------------------------

class CoverageFinding(BaseModel):
    index: int
    verdict: CoverageVerdict
    p_covered: float = Field(description="0..1. Your probability the Policy covers "
                                         "this item. UNSTATED sits near 0.75.")
    clause_verbatim: str | None = Field(
        description="Characters copied EXACTLY from the Policy. Null iff UNSTATED."
    )
    clause_locator: str | None = Field(description="e.g. 'Section 2.1', else null")
    exclusion_kind: str | None = Field(
        description="When NOT_COVERED: the named exclusion family, e.g. "
                    "'Verschleiss', 'Grundwasser', 'Neu fuer Alt'. Else null."
    )
    deductible_eur: float | None = Field(description="Recorded, never applied.")
    sublimit_eur: float | None = Field(description="Recorded, never applied.")

    @field_validator("p_covered")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        return min(1.0, max(0.0, v))

    @model_validator(mode="after")
    def _negative_verdict_needs_a_clause(self) -> "CoverageFinding":
        # ADR 0001: "the policy clause quoted verbatim". A NOT_COVERED with no
        # quote is exactly the hallucinated exclusion that drives the Limit to
        # zero and makes us pay 1.5a on every fair claim (README R7, and
        # strat-adjuster kill criterion 2). Demote rather than reject: an
        # exception at T+8s costs the whole gate.
        if self.verdict is CoverageVerdict.NOT_COVERED and not self.clause_verbatim:
            object.__setattr__(self, "verdict", CoverageVerdict.UNSTATED)
            object.__setattr__(self, "p_covered", max(self.p_covered, 0.6))
        return self


class CoverageReport(BaseModel):
    findings: list[CoverageFinding]
    prompt_version: str
    framing: str


# --- relatedness --------------------------------------------------------------

class RelatednessFinding(BaseModel):
    index: int
    verdict: RelatednessVerdict
    p_related: float = Field(description="0..1")
    evidence_verbatim: str | None = Field(
        description="The sentence of the Damage Description you relied on, "
                    "copied exactly. Null when the description is silent."
    )
    qty_expected_lo: float | None = Field(
        description="80% interval on the quantity the DESCRIPTION implies, in "
                    "the item's own unit. Null when it implies nothing."
    )
    qty_expected_hi: float | None
    reason: str | None


class RelatednessReport(BaseModel):
    findings: list[RelatednessFinding]
    prompt_version: str


# --- price: the band with named anchors --------------------------------------

class PriceAnchor(BaseModel):
    """One NAMED component of the price view. ADR 0001's 'named anchors'.

    An anchor is not an explanation. The engine reconciles the build-up
    (MATERIAL + HOURLY_RATE x TIME_PER_UNIT) against the band, and the residual
    is a term in sigma (3.3). Per R4b, sigma is what determines our score — so
    the anchors are the load-bearing half of this schema, not the prose half.
    """
    kind: AnchorKind
    label: str = Field(description="e.g. 'Bodenleger', 'AC4 laminate', 'Zeitansatz'")
    lo: float | None = Field(description="Null only for a TRADE anchor.")
    mid: float | None
    hi: float | None
    unit: str = Field(description="'EUR/h' | 'h/unit' | 'EUR/unit' | 'trade'")
    provenance: Provenance
    memory_key: str | None = Field(
        description="REQUIRED when provenance is PRICE_MEMORY: the exact key of "
                    "the retrieved row you used. Null otherwise."
    )
    basis_note: str | None = Field(
        description="Say so if you converted a gross figure: 'gross 25 EUR /1.19'."
    )

    @model_validator(mode="after")
    def _ordered(self) -> "PriceAnchor":
        """Sort lo/mid/hi into order, leaving Nones where they were.

        A model that swaps two of them is common and harmless; a model whose
        `lo` exceeds its `hi` would produce a NEGATIVE sigma downstream, which
        is not harmless. Fix here, once, rather than defending in assemble.py.
        """
        present = [(k, v) for k, v in (("lo", self.lo), ("mid", self.mid), ("hi", self.hi))
                   if v is not None]
        for (k, _), v in zip(present, sorted(v for _, v in present)):
            object.__setattr__(self, k, v)
        return self


class PriceFinding(BaseModel):
    index: int
    trade: str
    unit: Unit = Field(description="The unit your rate is PER. Normally the "
                                   "invoice's own unit; say so in `unit_note` "
                                   "if you had to change it.")
    unit_note: str | None
    net_unit_lo: float = Field(description="NET, per single unit. 80% interval.")
    net_unit_mid: float
    net_unit_hi: float
    anchors: list[PriceAnchor]
    deviation_factor: float = Field(
        description="Multiplier on the supplied REFERENCE BAND, in [0.6, 1.6]. "
                    "1.0 when the wording justifies no move, and when no "
                    "reference band was supplied."
    )
    deviation_reason: str | None
    overlaps_index: int | None = Field(
        description="Index of another Line Item whose scope already contains "
                    "this one (Doppelabrechnung), else null."
    )

    @field_validator("deviation_factor")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return min(1.6, max(0.6, v))

    @model_validator(mode="after")
    def _band_ordered_and_positive(self) -> "PriceFinding":
        lo, mid, hi = sorted(
            max(1e-6, x) for x in (self.net_unit_lo, self.net_unit_mid, self.net_unit_hi)
        )
        object.__setattr__(self, "net_unit_lo", lo)
        object.__setattr__(self, "net_unit_mid", mid)
        object.__setattr__(self, "net_unit_hi", hi)
        return self


class PriceReport(BaseModel):
    findings: list[PriceFinding]
    prompt_version: str
    framing: str


# --- image --------------------------------------------------------------------

class ImageReport(BaseModel):
    """Categorical only. There is deliberately NO numeric field in this class:
    strat-adjuster F5 — the photograph is a stock image and may not even match
    the Case. A schema that cannot express a measurement cannot be talked into
    producing one."""
    peril_depicted: str
    room_type: str | None
    severity: str                       # COSMETIC | STRUCTURAL | INDETERMINATE
    matches_description: bool
    mismatch_confidence: float
    prompt_version: str


# --- the packet the engine actually eats --------------------------------------

class LineItemEvidence(BaseModel):
    """Everything known about one Line Item, from every gate that returned.

    Every field is Optional-by-absence on purpose: a gate that timed out is a
    MISSING UPDATE, not a failure (4.5). The engine prices from whatever landed.
    """
    index: int
    pos: str
    description: str
    qty: float | None
    unit: Unit
    coverage: list[CoverageFinding]      # one per framing that returned
    relatedness: RelatednessFinding | None
    price: list[PriceFinding]            # one per framing that returned
    image: ImageReport | None            # Case-level, copied down for locality
    kb_id: str | None                    # from the deterministic canonicaliser
    kb_band: tuple[float, float, float] | None   # NET per unit, the reference band
    kb_sigma_log: float | None
    match_confidence: float              # canonicaliser: 1.0 exact .. 0.4 generic
    retrieved_memory_keys: frozenset[str]        # what we ACTUALLY injected (5.4)


class CaseEvidence(BaseModel):
    game_id: str
    trade: str | None
    items: list[LineItemEvidence]
    prompt_versions: dict[str, str]      # gate name -> version, for R9 (5.2)
    gates_returned: frozenset[str]
    gates_timed_out: frozenset[str]
```

### 3.2 What this schema makes impossible, and what the engine still verifies

Three classes of defect are unrepresentable rather than merely discouraged:

1. **A Charge, a Limit or a Fair Value.** No field exists. This is ADR 0001.
2. **A measurement from a photograph.** `ImageReport` has no numeric field but
   `mismatch_confidence`.
3. **An unanchored magnitude.** `PriceFinding.deviation_factor` is clamped to
   `[0.6, 1.6]` by a validator that runs on our side of the wire, so a model that
   returns 12.0 gets 1.6 and a log line, not a Submission ten times too large.

Two more are _checked_ rather than prevented, because they need the Case to check
against, and both run in `assemble.py` before anything reaches the posterior:

```python
def verify_quotes(item: LineItemEvidence, policy: str, damage: str) -> LineItemEvidence:
    """Demote any finding whose 'verbatim' quote is not in the source document.

    This is what converts 'we asked the agent to quote the clause' into 'the
    agent quoted the clause'. A NOT_COVERED whose clause is not a substring of
    policy.txt is a hallucinated exclusion — the single most expensive failure
    on the coverage gate, because it drives the Limit to zero and we then pay
    1.5x every fair Charge (README R7).

    Whitespace-and-case normalised; German quotation marks folded. NOT fuzzy:
    a near-match is still an invention.
    """
    norm = lambda s: " ".join(s.lower().replace("„", '"').replace("“", '"').split())
    hay_policy, hay_damage = norm(policy), norm(damage)
    for f in item.coverage:
        if f.clause_verbatim and norm(f.clause_verbatim) not in hay_policy:
            f.verdict, f.p_covered, f.clause_verbatim = (
                CoverageVerdict.UNSTATED, max(f.p_covered, 0.6), None)
    r = item.relatedness
    if r and r.evidence_verbatim and norm(r.evidence_verbatim) not in hay_damage:
        r.evidence_verbatim = None
        r.p_related = min(max(r.p_related, 0.5), 0.9)
    return item


def strip_laundered_anchors(item: LineItemEvidence) -> LineItemEvidence:
    """Drop any anchor claiming PRICE_MEMORY whose key we did not inject (5.4)."""
    for f in item.price:
        f.anchors = [
            a for a in f.anchors
            if a.provenance is not Provenance.PRICE_MEMORY
            or (a.memory_key in item.retrieved_memory_keys)
        ]
    return item
```

### 3.3 The evidence → posterior transformation

This is the whole ADR in ~90 lines. Written out in full, because "the engine builds
a log-normal posterior from the evidence" is the sentence that has to be true.

```python
# src/wireclaim/assemble.py
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist, median

from wireclaim.evidence import AnchorKind, CoverageVerdict, LineItemEvidence, RelatednessVerdict

_N = NormalDist()
_Z80 = 2.0 * _N.inv_cdf(0.90)      # 2.5631: an 80% band spans +/-1.2816 sigma
VAT = 1.19                          # strat-adjuster 4.0(a): applied ONCE, here.


@dataclass(frozen=True)
class Calibration:
    """Everything R9 fits (strat-quant 3.2). Cold-start values are the defaults."""
    beta: float = 0.0        # global log-bias on the median (this is log kappa_R9)
    gamma: float = 2.0       # global spread multiplier; wide on purpose (R4b)
    delta0: float = 0.0      # Platt intercept on coverage probability
    delta1: float = 1.0      # Platt slope
    sigma_floor: float = 0.18            # non-negotiable (strat-quant 3.1)
    tau: float = 0.80        # prior log-sd of the category, for R6b shrinkage
    lam: float = 1.0         # weight on the agents' self-reported within-band width
    pi0_cap_unquoted: float = 0.35       # kill criterion 2, made structural
    qty_geometry_weight: float = 0.30    # strat-adjuster 3.4: ships at 0.3, R9 decides


@dataclass(frozen=True)
class Posterior:
    """t ~ pi0 * delta(0) + (1 - pi0) * LogNormal(mu, sigma).  Fair Value, gross."""
    pi0: float
    mu: float
    sigma: float

    def quantile(self, q: float) -> float:
        """Quantile of the MIXTURE. b = quantile(1/3) is R4 with no special case."""
        if q <= self.pi0:
            return 0.0
        return math.exp(self.mu + self.sigma * _N.inv_cdf((q - self.pi0) / (1.0 - self.pi0)))

    def survival(self, a: float) -> float:
        """G(a) = P(t >= a), the R5b objective's only input. Note G(0+) = 1 - pi0."""
        if a <= 0.0:
            return 1.0
        return (1.0 - self.pi0) * (1.0 - _N.cdf((math.log(a) - self.mu) / self.sigma))

    @property
    def ungated_median(self) -> float:
        """The Estimate IGNORING coverage doubt — R6c's target on an uncovered
        Line Item: the number a competent-but-ungated team believes is fair, and
        therefore where the Field's Limits are densest."""
        return math.exp(self.mu)


def _platt(p: float, cal: Calibration) -> float:
    p = min(0.999, max(0.001, p))
    z = cal.delta0 + cal.delta1 * math.log(p / (1.0 - p))
    return 1.0 / (1.0 + math.exp(-z))


def _coverage_probability(item: LineItemEvidence, cal: Calibration) -> tuple[float, float]:
    """-> (pi_cov, sigma_disagreement). Two framings; their spread is real signal."""
    if not item.coverage:
        return 0.80, 0.10                       # gate missing: the prior, widened (4.5)
    ps = [_platt(f.p_covered, cal) for f in item.coverage]
    pi_cov = sum(ps) / len(ps)
    quoted = any(f.verdict is CoverageVerdict.NOT_COVERED and f.clause_verbatim
                 for f in item.coverage)
    if not quoted:
        # No verbatim exclusion survived verify_quotes -> pi0 may not exceed the
        # cap. Hallucinated exclusions are ~8x more expensive than missed ones.
        pi_cov = max(pi_cov, 1.0 - cal.pi0_cap_unquoted)
    return pi_cov, (max(ps) - min(ps)) / 2.0


def _relatedness(item: LineItemEvidence, cal: Calibration) -> tuple[float, float]:
    """-> (pi_rel, kappa_qty). kappa_qty haircuts the band for excess scope."""
    r = item.relatedness
    if r is None:
        return 0.90, 1.0                        # gate missing: the prior (4.5)
    pi_rel = r.p_related
    kappa = 1.0
    if r.verdict is RelatednessVerdict.SCOPE_EXCESSIVE and r.qty_expected_hi and item.qty:
        # The model states the expected quantity; the ENGINE does the arithmetic.
        raw = min(1.0, r.qty_expected_hi / item.qty)
        kappa = 1.0 - cal.qty_geometry_weight * (1.0 - raw)
    if item.image is not None and item.image.matches_description:
        pi_rel *= 1.05 if item.image.peril_depicted != "INDETERMINATE" else 1.0
    return min(1.0, pi_rel), max(0.7, kappa)


# Small-job reference quantity per unit (strat-adjuster 3.5). Below it, per-unit
# rates rise steeply because setup and travel stop amortising.
_QTY_REF = {Unit.SQM: 15.0, Unit.LM: 20.0, Unit.EACH: 3.0, Unit.HOUR: 3.0,
            Unit.DAY: 1.0, Unit.M3: 3.0, Unit.KG: 50.0, Unit.AW: 10.0,
            Unit.FLAT: 1.0, Unit.PCT: 1.0, Unit.UNKNOWN: 1.0}


def _framing_mu_sigma(f, item, cal) -> tuple[float, float, float]:
    """One price framing -> (mu_k, sigma_k, iota_k).

    mu_k    log of the GROSS line total this framing implies
    sigma_k the framing's OWN stated width, from its 80% band
    iota_k  the reconciliation residual between the NAMED ANCHORS' build-up and
            the framing's market band. THIS is what ADR 0001's 'named anchors'
            buy us: a second, independent estimate whose disagreement with the
            first is a measurement of how much the framing actually knows.
            Per R4b that measurement, not the centre, is what we are paid on.
    """
    qty = item.qty if item.qty and item.qty > 0 else 1.0
    band = f.deviation_factor * f.net_unit_mid
    if item.kb_band is not None:
        # A reference band existed, so deviation_factor is a multiplier ON IT and
        # the framing's own mid is a second opinion. Geometric blend: the KB is a
        # sourced prior, the framing is a fresh read, neither dominates.
        band = math.sqrt((f.deviation_factor * item.kb_band[1]) * (f.net_unit_mid))
    f_small = 1.0 + 0.8 * max(0.0, 1.0 - qty / _QTY_REF[item.unit])
    mu_k = math.log(qty * band * f_small * VAT)
    sigma_k = (math.log(f.net_unit_hi) - math.log(f.net_unit_lo)) / _Z80

    iota_k = 0.0
    rate = next((a for a in f.anchors if a.kind is AnchorKind.HOURLY_RATE), None)
    time = next((a for a in f.anchors if a.kind is AnchorKind.TIME_PER_UNIT), None)
    matl = next((a for a in f.anchors if a.kind is AnchorKind.MATERIAL), None)
    if rate and time and rate.mid and time.mid:
        buildup = rate.mid * time.mid + (matl.mid if matl and matl.mid else 0.0)
        if buildup > 0:
            # Clipped at 0.9 in log space: strat-adjuster 4.0(c) documents that a
            # raw labour-minute build-up runs ~8x under a market unit rate for
            # good structural reasons (setup, waste, travel, overhead, margin).
            # A large residual is therefore weak evidence, not proof of error —
            # but a framing whose two views agree exactly has told us nothing.
            iota_k = min(0.9, abs(math.log(buildup / f.net_unit_mid)))
    return mu_k, sigma_k, iota_k


def evidence_to_posterior(item: LineItemEvidence, cal: Calibration,
                          category_mu: float | None) -> Posterior:
    """THE transformation. Evidence in, Posterior out. Pure, total, testable."""
    # --- 1. the spike at zero (R6c) -------------------------------------------
    pi_cov, sig_cov = _coverage_probability(item, cal)
    pi_rel, kappa_qty = _relatedness(item, cal)
    pi0 = min(0.98, max(0.0, 1.0 - pi_cov * pi_rel))

    # --- 2. the continuous part, from the bands and the anchors ---------------
    if not item.price:
        # No price framing returned. Fall back to the KB band alone, wide.
        if item.kb_band is None:
            # Nothing at all: the trade-and-unit generic band (D3's
            # `TRADE.__DEFAULT__.<UNIT>` row), which never fails and never
            # returns nothing. sigma 0.75 says so honestly.
            lo, mid, hi = generic_band(item.unit, trade=item.kb_id)
            return Posterior(pi0=pi0, mu=math.log((item.qty or 1.0) * mid * VAT), sigma=0.75)
        qty = item.qty or 1.0
        return Posterior(pi0=pi0, mu=math.log(qty * item.kb_band[1] * VAT), sigma=0.55)

    triples = [_framing_mu_sigma(f, item, cal) for f in item.price]
    mus = [t[0] for t in triples]
    mu_raw = median(mus)
    dev = sorted(abs(m - mu_raw) for m in mus)
    s_between = 1.4826 * median(dev)                      # robust to one rogue framing
    s_within = math.sqrt(sum(t[1] ** 2 for t in triples) / len(triples))
    iota = sum(t[2] for t in triples) / len(triples)      # anchor/band reconciliation
    s_match = 0.22 * (1.0 - item.match_confidence)        # 0 on an exact KB alias hit
    s_image = 0.0
    if item.image is not None and not item.image.matches_description:
        s_image = 0.08                                    # a photo we cannot trust
    sigma_raw = math.sqrt(s_between**2 + cal.lam * s_within**2 + iota**2
                          + s_match**2 + sig_cov**2 + s_image**2)

    # --- 3. scope haircut, overlap haircut, image severity --------------------
    mu = mu_raw + math.log(kappa_qty)
    if any(f.overlaps_index is not None for f in item.price):
        mu += math.log(0.55)          # Doppelabrechnung: marginal content only
    if item.image is not None and item.image.matches_description:
        if item.image.severity == "STRUCTURAL":
            mu += math.log(1.20)
        elif item.image.severity == "COSMETIC":
            mu += math.log(0.85)

    # --- 4. global calibration (R9) ------------------------------------------
    mu += cal.beta                                        # log kappa_R9
    sigma = max(cal.gamma * sigma_raw, cal.sigma_floor)

    # --- 5. shrinkage toward the category median (R6b) ------------------------
    if category_mu is not None:
        w = cal.tau**2 / (cal.tau**2 + sigma**2)          # 0.76 at tau=.8, sigma=.45
        mu = category_mu + w * (mu - category_mu)

    return Posterior(pi0=pi0, mu=mu, sigma=sigma)
```

Read step 2 again, because it is the answer to ADR 0001's own stated worry. σ is
built from five _measured_ disagreements and not one self-report:

| term        | what disagrees                                                 | why it is honest                                                                                               |
| ----------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `s_between` | the three price framings with each other                       | different estimators, so correlated error is the only way to fool it                                           |
| `s_within`  | each framing's own 80 % band                                   | the weakest term, hence `lam` is fitted and starts at 1                                                        |
| `iota`      | **each framing's anchor build-up against its own market band** | the named anchors' entire purpose; ADR 0001's "band with named anchors" is a _second estimate_, not a footnote |
| `s_match`   | the canonicaliser's confidence in the KB row                   | deterministic, from string distance                                                                            |
| `sig_cov`   | the two coverage framings with each other                      | coverage doubt widens price width, correctly                                                                   |

And `sigma_floor = 0.18` is mandatory: three framings agreeing is not evidence of
accuracy — they share training data, and correlated error is invisible to
between-framing variance.

### 3.4 How coverage confidence becomes a spike at zero (R6c)

`t = 0` when the Policy does not cover the item. That is not "a low price", it is a
**different kind of object**, and collapsing it early is how a pipeline gets R6c
wrong. So the coverage verdict never becomes a boolean and never multiplies the
price. It becomes `π₀`, the mass the posterior puts _exactly at zero_, and every
downstream rule reads it out of the mixture with no special case:

```python
# src/wireclaim/decide.py  (deterministic; consumes Posterior, emits the Submission)

# 200 log-spaced grid points spanning +/-3 sigma of the posterior. Fixed, so the
# argmax is reproducible to the cent across runs and machines (5.1).
_LOG_GRID = [-3.0 + 6.0 * k / 199 for k in range(200)]

def _round_eur(x: float) -> float:
    """Round to the cent, half-up. The wire wants a number; float noise in the
    17th digit is one more way two runs disagree."""
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def limit(post: Posterior) -> float:
    """R4: b = Q(1/3) of the posterior on Fair Value. R6: bottom third, then stop.

    The mixture does the uncovered-item logic for free: when pi0 >= 1/3 the
    one-third quantile IS zero, so 'reject outright what we believe is not
    covered' needs no if-statement in the strategy. That the payoff matrix's
    2/3 acceptance bar and the coverage gate's own 2/3 arrive at the same
    number from opposite directions is the nicest thing on the slide.
    """
    return post.quantile(1.0 / 3.0)


def charge(post: Posterior, p_curve: AcceptanceCurve | None, cap_hint: float | None) -> float:
    """R5b argmax, with R6c's free option and R5c's p-gate.

    R5c is the expensive lesson: a mis-measured acceptance rate cost ~60% of net
    in simulation. So p is ZERO unless an acceptance curve measured from settled
    Games says otherwise, with enough support to trust it (`p_curve.trusted`).
    """
    p = p_curve if (p_curve is not None and p_curve.trusted) else None

    # R6c: the item is probably not covered -> t = 0 -> honest income is exactly
    # zero and a rejected Overcharge costs exactly nothing. Charging is weakly
    # dominant in EVERY phase, overnight included. Aim at the number an ungated
    # team believes is fair, because that is where the Field's Limits are densest
    # -- not at infinity, which only depresses p(x) for no extra payoff.
    if post.pi0 >= 0.5:
        target = post.ungated_median
        return _round_eur(min(target, cap_hint) if cap_hint else target)

    grid = [math.exp(post.mu + z * post.sigma) for z in _LOG_GRID]   # 200 points
    def ev(a: float) -> float:
        g = post.survival(a)
        if p is None:
            return a * g                                   # honest arm only
        return a * g + min(a, cap_hint or a) * (1.0 - g) * p.at(a)
    return _round_eur(max(grid, key=ev))
```

Two properties of this that are worth stating out loud, because they are the whole
reason π₀ is carried rather than collapsed:

- **The Limit falls off a cliff and the Charge does not.** At `π₀ ≥ 1/3` the Limit
  is exactly 0 — we refuse to pay for what we believe is uncovered. But at
  `π₀ ≥ 0.5` the Charge _rises_ to the ungated median, because R6c says charging on
  an uncovered item is free. One number, two opposite behaviours, no branching in
  the strategy layer. A pipeline that emitted a boolean "covered: false" could
  express neither.
- **Between `π₀ = 0.33` and `π₀ = 0.5` the machine hedges automatically**: Limit
  already zero, Charge still the honest argmax. That band is where a coverage gate
  that is merely unsure lands, and hedging is the right thing to do there.

### 3.5 Worked example — QuantCo's own slide, Line Item 1

`Remove water-damaged laminate in living room · 18 · m²`, Policy covers water
damage to floor coverings, description says the living-room floor was soaked.

```
coverage_strict     COVERED  p=0.95  clause "...Schaeden an Bodenbelaegen infolge..."
coverage_charitable COVERED  p=0.97  same clause                    -> pi_cov 0.96, sig_cov 0.01
relatedness         RELATED  p=0.93  "...soaked over roughly 18 m2"  -> pi_rel 0.93, kappa 1.0
                                                                    -> pi0 = 1 - 0.893 = 0.107

price/sachverstaendiger  net_unit 5.5 / 9.0 / 15.0   dev 1.15  anchors: Bodenleger,
                         48 EUR/h, 0.10 h/m2, disposal 3.00     -> buildup 7.80 vs band 9.00
price/kalkulator         net_unit 6.0 / 8.5 / 12.0   dev 1.15   -> iota 0.14 / 0.05 / 0.31
price/einkaeufer         net_unit 3.5 / 6.5 / 11.0   dev 1.00

kb FLOOR.LAMINATE.REMOVE  band (4.0, 8.0, 13.0)  sigma_kb 0.28  match 1.0

mu_k        = ln(18 x sqrt(1.15x8.0 x 9.0) x f_small(1.13) x 1.19)  = ln(220.4) etc
mu_raw      = 5.34   (~208 EUR gross)
s_between   = 0.11   s_within = 0.21   iota = 0.17   s_match = 0   sig_cov = 0.01
sigma_raw   = sqrt(0.11^2 + 0.21^2 + 0.17^2)                        = 0.29
sigma       = max(2.0 x 0.29, 0.18) = 0.58   <- gamma=2.0 COLD START, before any label
                                                after ~15 settled Games gamma -> ~0.85
                                                and sigma -> 0.25 (strat-adjuster 2.3)

Limit  = Q(1/3) of the mixture, pi0=0.107 -> exp(5.34 + 0.58 x Phi^-1(0.254)) = 150 EUR
Charge = argmax a x G(a), p=0 overnight   -> 0.69 x exp(mu) = 145 EUR
```

Note `Charge < Limit` overnight — `strat-adjuster` §2.3 point 3, and the opposite of
what a team that hard-coded "aggressive as issuer, timid as reviewer" will submit.

---

## 4. Workflow topology and the latency budget

### 4.1 The graph

```python
# src/wireclaim/adk/graph.py
"""START -> six or seven gates in parallel -> JoinNode. That is the whole shape.

A Workflow graph rather than SequentialAgent(ParallelAgent(...)) because
google-adk 2.7.1 deprecates both, and because per-node retry and per-node
timeout are exactly what a 60-second budget needs (SampleRepo ADR 0028 D2).
"""
from google.adk.agents import LlmAgent
from google.adk.workflow import START, JoinNode, RetryConfig, Workflow

# ONE attempt, ONE retry 0.6s later. Not SampleRepo's 3 attempts at 2s/4s:
# their ceiling is 300s, ours is 35s. jitter=0.0 because a retry schedule that
# varies run to run is one more thing between us and 5.1's determinism claim.
GATE_RETRY = RetryConfig(max_attempts=2, initial_delay=0.6, backoff_factor=2.0, jitter=0.0)

# Per-node wall-clock ceilings. LlmAgent IS a workflow BaseNode (BaseAgent
# subclasses BaseNode in 2.7.1), so `timeout` is a field on the agent itself and
# a breach raises NodeTimeoutError, which GATE_RETRY then retries once.
TIMEOUTS = {"coverage": 9.0, "relatedness": 8.0, "price": 10.0, "image": 11.0}


class _BestEffortGate(LlmAgent):
    """A gate whose failure leaves its slot empty instead of killing the run.

    SampleRepo ADR 0028 D3, and load-bearing here for a harder reason than
    there: a node that raises sets `error_shut_down` and stops the whole graph,
    which would mean one flaky gate costs us EVERY gate — and the engine can
    price from partial evidence (4.5) but not from none.

    Unlike SampleRepo, ALL our nodes are best-effort. They had a narrator
    whose failure meant there was nothing to salvage; our terminal node is a
    JoinNode and our salvage path is the Fast Path Submission already on file.
    """

    async def _run_impl(self, *, ctx, node_input):          # type: ignore[override]
        try:
            async for event in super()._run_impl(ctx=ctx, node_input=node_input):
                yield event
        except Exception as e:                              # noqa: BLE001 — the point
            logger.warning("gate %s failed; pricing without it: %s", self.name, e)


def _gate(agent: LlmAgent, output_key: str, timeout: float) -> LlmAgent:
    agent.__class__ = _BestEffortGate      # safe: the subclass adds no pydantic field
    agent.output_key = output_key          # -> session.state[output_key]
    agent.retry_config = GATE_RETRY
    agent.timeout = timeout
    return agent


def evidence_workflow(*, with_image: bool) -> Workflow:
    """The Slow Path graph. Extraction has already happened (4.2)."""
    nodes = [
        _gate(coverage_agent("strict"),      "cov_strict",  TIMEOUTS["coverage"]),
        _gate(coverage_agent("charitable"),  "cov_charit",  TIMEOUTS["coverage"]),
        _gate(relatedness_agent(),           "rel",         TIMEOUTS["relatedness"]),
        _gate(price_evidence_agent("sachverstaendiger"), "pri_sv",  TIMEOUTS["price"]),
        _gate(price_evidence_agent("kalkulator"),        "pri_kal", TIMEOUTS["price"]),
        _gate(price_evidence_agent("einkaeufer"),        "pri_eink",TIMEOUTS["price"]),
    ]
    if with_image:
        nodes.append(_gate(image_agent(), "img", TIMEOUTS["image"]))

    # The JoinNode is load-bearing, not decoration: seven edges landing on one
    # successor would trigger it seven times (SampleRepo ADR 0028 D4). Here it
    # is also the TERMINAL node — we have no narrator, because a narrator is
    # exactly the thing ADR 0001 forbids. Evidence goes to the engine, not to
    # another model.
    join = JoinNode(name="evidence_join")
    return Workflow(
        name="evidence_workflow",
        edges=[(START, n) for n in nodes] + [(n, join) for n in nodes],
        max_concurrency=None,              # all gates genuinely concurrent
    )
```

```python
# src/wireclaim/adk/runtime.py  (the parts that differ from SampleRepo's)

async def _run_evidence(workflow, prompt: str, images: list[bytes]) -> dict:
    """Drive the graph once and return the SESSION STATE, not the final text.

    SampleRepo's run_workflow parses the terminal narrator's JSON. Our
    terminal node is a JoinNode, so there is no prose to parse — each gate has
    already written its structured output to session.state under its
    `output_key`. Reading state is both more honest and more robust: a gate
    that landed is readable even if a later one exploded.
    """
    runner = InMemoryRunner(agent=workflow, app_name=_APP)
    session = await runner.session_service.create_session(app_name=_APP, user_id=_USER)
    parts = [types.Part(text=prompt)] + [
        types.Part(inline_data=types.Blob(mime_type="image/png", data=b)) for b in images
    ]
    async for _ in runner.run_async(user_id=_USER, session_id=session.id,
                                    new_message=types.Content(role="user", parts=parts)):
        pass
    final = await runner.session_service.get_session(
        app_name=_APP, user_id=_USER, session_id=session.id)
    return dict(final.state)


def run_evidence(workflow, prompt: str, images: list[bytes], budget_s: float) -> dict:
    """Sync front door. NO outer retry: a Workflow owns retry per node, so the
    node that failed is the node that re-runs (ADR 0028 D2/D6). `budget_s`
    bounds the WHOLE graph, not one attempt — on breach the future is CANCELLED,
    not merely abandoned, so a dead run stops burning the 60-second window.
    """
    _ensure_provider_env()
    return _sync_run(lambda: _run_evidence(workflow, prompt, images), timeout=budget_s)
```

### 4.2 Why extraction is outside the graph

`invoice_extractor` is not a node. Extraction runs before the graph, synchronously,
because:

1. **The Fast Path needs it first.** A Submission must be on file at T+1.6 s, and
   the Fast Path prices from the extracted Line Items. If extraction were a graph
   node, it would run after the Fast Path deadline.
2. **The graph's `node_input` is the extracted Case.** Every gate needs the Line
   Item list; a graph that extracts and then fans out is a two-stage graph whose
   first stage is deterministic 95 % of the time.
3. **The fallback rung is conditional.** Rung 4 fires only when rungs 1–3 fail —
   an `if`, in Python, where it is testable, not a routing decision inside a graph.

So: `extract() -> Case` (deterministic ladder, with rung 4 calling the extractor
agent through a one-node run), then Fast Path Submission, then
`evidence_workflow(with_image=case.images != ())` with the Case as input.

### 4.3 The latency budget

Times are wall clock from the Game opening at T+0. Rows above the Fast Path
Submission are `strat-adjuster` §6.2 unchanged; this document owns the rows below
it.

| Phase                                                   | p50         | p95         | On breach                       |
| ------------------------------------------------------- | ----------- | ----------- | ------------------------------- |
| key → decrypt → read → extract → canonicalise           | 0.5 s       | 1.3 s       | ladder rungs 2/3/4              |
| **Fast Path Submission (the floor)**                    | **T+1.1 s** | **T+1.9 s** | retry 0.2/0.5/1/2 s             |
| build 4 prompts + retrieve Price Memory (deterministic) | 0.05 s      | 0.1 s       | memory skipped, flagged         |
| graph launched at T+1.2 s — all gates concurrent        |             |             |                                 |
| ├ coverage ×2 (`REASONING`, short doc)                  | 3.5 s       | 7 s         | node timeout 9 s, 1 retry       |
| ├ relatedness (`FAST`)                                  | 2.5 s       | 5 s         | node timeout 8 s, 1 retry       |
| ├ price ×3 (`REASONING`, bounded output)                | 4.5 s       | 9 s         | node timeout 10 s, 1 retry      |
| └ image (`VISION`, only if present)                     | 6 s         | 11 s        | node timeout 11 s, **no retry** |
| join + `verify_quotes` + `strip_laundered_anchors`      | <5 ms       | 10 ms       | —                               |
| `evidence_to_posterior` × N items                       | <1 ms       | 2 ms        | —                               |
| `charge()` 200-point grid × N items                     | <1 ms       | 3 ms        | —                               |
| **Slow Path Submission**                                | **T+7 s**   | **T+14 s**  | —                               |
| graph budget breach → cancel, price from what landed    |             | T+24 s      | Submission at T+25 s            |
| **hard cut — nothing is sent after this**               |             |             | **T+48 s**                      |

Worst case with one retry on the slowest node: `1.2 + 10 + 0.6 + 10 = 21.8 s`,
inside the 24 s graph budget, inside the 48 s hard cut, with 12 s of slack for the
POST and its backoff. The image node gets no retry precisely because it is the one
node that can push past the budget on its own, and per `strat-adjuster` §6.5 it is
also the node we most expect to delete.

**The guard that makes the whole graph safe** (`strat-adjuster` §6.4, restated here
because it is the licence to build any of this): the Slow Path Submission replaces
the Fast Path one **only if** every returned gate parsed as valid JSON _and_ the
resulting Charge lies within ×[0.3, 3.0] of the Fast Path Charge. Outside that band
we keep the floor and log loudly. The elaborate pipeline's real risk is not that it
is slow; it is that it is confidently wrong where the simple path was not.

### 4.4 What the engine can still price from — the partial-evidence table

A missing gate is a missing _update_, not a failure. That is the payoff of three
independent gates over one mega-prompt, and it is why `LineItemEvidence` makes every
gate optional.

| Missing                        | Engine substitutes                  | σ effect                          | Still submits?                                                                      |
| ------------------------------ | ----------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------- |
| one coverage framing           | the other framing alone             | `sig_cov = 0.10` floor            | yes, unchanged                                                                      |
| **both** coverage framings     | `π_cov = 0.80` prior                | `+0.10`                           | yes — **and π₀ is capped at 0.35**, so a coverage blackout can never zero the Limit |
| relatedness                    | `π_rel = 0.90`, `κ_qty = 1.0`       | none                              | yes                                                                                 |
| one price framing              | median over the other two           | `s_between` from 2 points         | yes                                                                                 |
| two price framings             | the single framing's own band       | `s_between = 0`, `lam` carries it | yes, wider                                                                          |
| **all three** price framings   | KB band, `σ = 0.55`                 | —                                 | yes — this is the Fast Path's own estimate                                          |
| KB entry absent (`kb_id` null) | framings' own bands, no blend       | `s_match` up                      | yes                                                                                 |
| image                          | nothing; `π_rel` and band unchanged | none                              | yes                                                                                 |
| **every gate**                 | the Fast Path Submission stands     | —                                 | yes, already on file                                                                |

The bottom row is the important one. The pipeline cannot cost us a Game; it can only
fail to improve one.

---

## 5. Determinism and testing

### 5.1 What is deterministic, and what is only reproducible — stated honestly

Three different claims, and conflating them is how a team ends up believing
something untrue at 04:00:

| Claim                                                    | Status                                          | Mechanism                                                                                                                                                                                                           |
| -------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Identical evidence ⇒ identical Submission**            | **Guaranteed.** A theorem about pure functions. | `assemble.py` + `decide.py` are pure, total, stdlib-only, no clock, no RNG, no I/O                                                                                                                                  |
| **Identical Case ⇒ identical evidence**                  | **Not guaranteed by any provider.**             | temperature 0 makes it likely, not certain; ADK's `OpenAILlm` does not forward a `seed` (verified: `_openai_llm.py` passes model/messages/tools/tool_choice/max_tokens/response_format/temperature/top_p/stop only) |
| **Identical Case ⇒ identical Submission, in our system** | **Guaranteed after the first run.**             | the evidence cache: a Case fingerprint hits stored evidence and replays it                                                                                                                                          |

We assert the first and the third in tests, and we _do not claim_ the second. That
distinction is also the pitch's most credible slide: everyone else will claim
determinism they do not have.

```python
DETERMINISTIC = types.GenerateContentConfig(
    temperature=0.0,
    top_p=1.0,
    max_output_tokens=4096,
    # NOTE: response_schema must NOT be set here — LlmAgent's own validator
    # rejects it and demands `output_schema=`. Same for tools and
    # system_instruction. (llm_agent.py: validate_generate_content_config)
)
```

The evidence cache is SampleRepo's `cached_single_flight` with the TTL removed
and the key changed:

```python
def evidence_key(case: Case) -> str:
    """A Case fingerprint. Includes every prompt version, because evidence
    produced under prompt 'cov-3' is not evidence about prompt 'cov-4' (5.2)."""
    body = sha256(
        b"|".join([case.policy_text.encode(), case.damage_text.encode(),
                   *(f"{i.pos}|{i.description}|{i.qty}|{i.unit}".encode() for i in case.items),
                   *(sha256(p.read_bytes()).digest() for p in case.images)])
    ).hexdigest()[:24]
    return f"evidence:{body}:{PROMPT_VERSION_FINGERPRINT}"
```

Two things fall out for free. A re-run of a Game replays evidence instead of paying
for it — which is what makes the counterfactual evaluator (`strat-quant` §3.7)
possible at all, since we can re-price a whole night of settled Games under a new
`Calibration` in milliseconds and with no API calls. And the redundant second runner
on a second machine (`strat-adjuster` §5.2) produces a byte-identical payload from
the same shared evidence store, which is what makes redundancy free rather than a
source of disagreement.

### 5.2 Prompt-version constants

Every version constant from §2.1 is copied into three places: the evidence packet
(`CaseEvidence.prompt_versions`), the evidence cache key, and the Price Memory row.

The reason is not hygiene, it is arithmetic. `strat-quant` §3.2 fits `(β, γ, δ₀, δ₁)`
by maximum likelihood on interval-censored labels from settled Games. Fitting across
a prompt change is fitting on two different instruments and will silently produce a
worse calibration than not fitting at all. So the fit is scoped to a prompt-version
fingerprint, and changing a prompt mid-tournament **resets that fingerprint's
observation count to zero** — which, given the ≥ 40-observation guardrail, means the
next few Games run on the previous calibration. That is the honest cost of touching
a prompt after Game 20, and it should make us not want to.

### 5.3 The tests

```python
# tests/test_determinism.py

def test_identical_evidence_yields_identical_submission():
    """ADR 0001's central consequence, asserted. No provider, no network."""
    ev = load_fixture("evidence/case0.json")          # a frozen CaseEvidence
    cal = Calibration()
    first  = [submission_for(i, cal) for i in ev.items]
    second = [submission_for(i, cal) for i in ev.items]
    assert first == second
    # ...and stable across process boundaries, which set iteration order is not:
    assert sha256(json.dumps(first, sort_keys=True).encode()).hexdigest() == FROZEN_DIGEST


def test_the_engine_is_a_pure_function_of_evidence_and_calibration():
    """No clock, no RNG, no environment. Guards against the failure where a
    future 'small tweak' reads datetime.now() for a phase and silently makes
    the night's Submissions unreproducible."""
    ev, cal = load_fixture("evidence/case0.json"), Calibration()
    with freeze_time("2026-08-23 03:17:00"), patched_random(seed=1):
        a = [submission_for(i, cal) for i in ev.items]
    with freeze_time("2026-08-22 15:00:00"), patched_random(seed=999):
        b = [submission_for(i, cal) for i in ev.items]
    assert a == b


def test_no_agent_schema_can_express_a_price_decision():
    """ADR 0001 made structural. If someone adds `charge` to PriceFinding to
    'just get it working at 3am', this test is what stops it shipping."""
    banned = {"charge", "limit", "fair_value", "price", "total", "gross",
              "amount", "a", "b", "t", "bid", "offer", "recommendation"}
    for model in (CoverageFinding, RelatednessFinding, PriceFinding,
                  PriceAnchor, ImageReport, ExtractedLineItem):
        assert not (banned & set(model.model_fields)), model.__name__


def test_uncovered_line_item_charges_and_refuses_to_pay():
    """R6c: t = 0 -> always Charge (free), and R4 -> Limit exactly 0.
    Both from ONE number, with no branch in the strategy layer."""
    post = Posterior(pi0=0.92, mu=math.log(300.0), sigma=0.4)
    assert limit(post) == 0.0
    assert charge(post, p_curve=None, cap_hint=None) == pytest.approx(300.0, rel=0.02)


def test_hallucinated_exclusion_cannot_zero_the_limit():
    """A NOT_COVERED whose clause is not in policy.txt is demoted to UNSTATED
    and pi0 is capped at 0.35, so the Limit stays positive. This is the failure
    that makes us pay 1.5a on every fair Charge (R7); it must be unreachable."""
    item = evidence_with_coverage(verdict="NOT_COVERED", p_covered=0.02,
                                  clause="Section 9.9 Wasserschaeden sind nicht versichert")
    item = verify_quotes(item, policy="(a policy that says no such thing)", damage="")
    post = evidence_to_posterior(item, Calibration(), category_mu=None)
    assert post.pi0 <= 0.35
    assert limit(post) > 0.0


def test_every_output_schema_survives_a_live_strict_round_trip():
    """Boot-time smoke test, marked `provider`. OpenAI strict mode rejects some
    JSON Schema keywords and requires `required` to list EVERY property. A
    schema that 400s is a schema that costs a Game at T+8s, so we find out at
    boot with one trivial call per schema, not in the window."""
    for schema in (ExtractedInvoice, CoverageReport, RelatednessReport,
                   PriceReport, ImageReport):
        assert round_trip_one_call(schema) is not None
```

Plus one property test worth its keep: `Posterior.quantile` is monotone in `q` and
`Posterior.survival` is its complement, over 10 000 random `(π₀, μ, σ)`. The mixture
arithmetic is the only clever code in the engine and it is where a sign error would
hide.

### 5.4 The Price Memory as retrieved context, without laundering

ADR 0001 flags this as a live risk: the Price Memory feeds the agents as context,
which creates a path for a remembered price to come back as if it were freshly
reasoned evidence. Then the engine would combine it with the memory _again_ and
double-count, producing a posterior far narrower than the evidence supports — which
per R4b is the exact failure that gets us farmed by an exploiter parked at the Cap.

Five mechanisms, in increasing order of how much they actually rely on the model
behaving:

**1. The gates that must not see a price, cannot.** Coverage and relatedness prompts
are built by `build_gate_prompt()`, which takes the Policy or the Damage Description
and the Line Item list, and has no parameter for memory. It is not possible to pass
it. Structural, not disciplinary.

**2. Retrieved anchors arrive fenced and labelled.**

```python
def build_price_prompt(item, memory_rows) -> tuple[str, frozenset[str]]:
    """-> (prompt, the keys we ACTUALLY injected). The second return value is
    the anti-laundering guard's ground truth and it is never derived from the
    model's reply."""
    block = "\n".join(
        f"  [{r.key}] {r.label}: net {r.lo:.2f}/{r.mid:.2f}/{r.hi:.2f} EUR per {r.unit}"
        f"  (recovered from {r.n_games} settled Games, last Game {r.last_game})"
        for r in memory_rows)
    prompt = (
        f"LINE ITEM\n  {item.pos} | {item.description} | {item.qty} {item.unit}\n\n"
        f"===== RETRIEVED PRIOR (NOT evidence you produced) =====\n{block}\n"
        f"These are OUR OWN earlier estimates, recovered from settled Games. They\n"
        f"are a prior, not a fact, and they may be wrong. Form your own view\n"
        f"first. If you then use one, you MUST return it as an anchor with\n"
        f"provenance PRICE_MEMORY and its bracketed key.\n"
        f"===== END RETRIEVED PRIOR =====\n")
    return prompt, frozenset(r.key for r in memory_rows)
```

**3. The engine verifies provenance by set membership, not by trust.**
`strip_laundered_anchors` (§3.2) drops any anchor claiming `PRICE_MEMORY` whose
`memory_key` is not in the set we injected. A model cannot invent a key it was not
shown, and a model that copies a retrieved number while labelling it
`MODEL_JUDGEMENT` is caught by the next mechanism.

**4. The memory-derived and the fresh views are combined by the engine, once, in
one place.** `_framing_mu_sigma` computes `mu_k` from the framing's band; anchors
with `provenance == PRICE_MEMORY` are **excluded from `iota`** (they are not an
independent build-up) and instead enter as a separate log-space Bayesian update
after §3.3 step 4, with a weight that is a function of the memory row's observation
count and nothing else:

```python
def apply_memory_prior(post: Posterior, rows, qty: float | None) -> Posterior:
    """One explicit update, with a weight the model cannot influence."""
    if not rows:
        return post
    mu_m = math.log(median([r.mid for r in rows]) * (qty or 1.0) * VAT)
    n = sum(r.n_games for r in rows)
    sigma_m = max(0.15, 0.60 / math.sqrt(n))            # shrinks with evidence, not confidence
    w = post.sigma**2 / (post.sigma**2 + sigma_m**2)    # precision-weighted, standard
    return Posterior(pi0=post.pi0,
                     mu=(1 - w) * post.mu + w * mu_m,
                     sigma=math.sqrt(1.0 / (1.0 / post.sigma**2 + 1.0 / sigma_m**2)))
```

Because the update happens exactly once, in the engine, a laundered anchor that
slipped through mechanism 3 can bias `mu_raw` slightly but **cannot** narrow σ
twice — the σ shrink comes only from `n`, the count of settled Games behind the row.
Double-counting is therefore bounded to the centre and cannot touch the width, which
per R4b is the quantity that can actually hurt us.

**5. It is measured, not assumed.** A canary: for 1 Game in 10, retrieval is
suppressed and the evidence is produced blind. If blind and retrieved evidence agree
far more closely than the memory's own `n` justifies, anchors are laundering, and
the dashboard says so. Cost: one Game in ten runs on a slightly weaker prior.

---

## 6. Provider decision

### 6.1 What is actually in the installed package

Inspected at
`WealthWatchter/server/.venv/lib/python3.13/site-packages/google/adk/models/` on
**google-adk 2.7.1 / google-genai 2.18.1**:

| Finding                                                                  | Detail                                                                                                                                                               |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ADK ships a first-class OpenAI model class**                           | `google/adk/labs/openai/_openai_llm.py::OpenAILlm`, exported from `google.adk.labs.openai`                                                                           |
| **It is auto-registered by model-id regex**                              | `models/__init__.py::_LAZY_PROVIDERS` maps `gpt-.*` and `o\d+-.*` to it. `LlmAgent(model="gpt-4o")` resolves with **zero** code change                               |
| **`output_schema` works**                                                | `generate_content_async` turns a Pydantic `response_schema` into OpenAI `{"type":"json_schema","strict":true,...}` via `_openai_schema.enforce_strict_openai_schema` |
| **`temperature` / `top_p` / `stop` / `max_output_tokens` are forwarded** | explicitly, from `llm_request.config`                                                                                                                                |
| **`seed` is NOT forwarded**                                              | the kwargs dict is model/messages/tools/tool_choice/max_tokens/response_format + those four. No seed. (§5.1)                                                         |
| **Vision works**                                                         | `_part_to_openai_content` base64-encodes `inline_data` into an `image_url` data URI                                                                                  |
| **`LiteLlm` is also present**                                            | `models/lite_llm.py`, registered for `openai/*`, `anthropic/*`, `azure/*`, `groq/*`, `bedrock/*`, `mistral/*`, `deepseek/*`, `ollama/*`, …                           |
| **Anthropic is also first-class**                                        | `models/anthropic_llm.py::Claude`, registered for `claude-3-*`, `claude-*-4*`, `claude-*-5*`                                                                         |
| **Neither `litellm` nor `openai` is installed in that venv**             | `LiteLlm` raises `ImportError` on import; `OpenAILlm` raises a clear "pip install openai"                                                                            |

Two constraints that follow and that we must design around:

- **Strict mode forces `required = every property`** (`enforce_strict_openai_schema`
  sets `additionalProperties: false` and `required = sorted(properties)`), so an
  optional field must be `X | None` and the prompt must say "emit null". §3.1 is
  already written this way.
- **`LlmCapabilities.output_schema_and_tools` is `False` by default** and true only
  for Vertex-AI Gemini (`_capabilities.gemini_output_schema_and_tools`). We use no
  tools in any agent, so this does not bite — but it forecloses a future "price
  agent with a KB-lookup function tool _and_ an output schema" on OpenAI. If we ever
  want that, the KB goes in the prompt, which is where it is anyway.

### 6.2 Recommendation

> **Ship on OpenAI via ADK's native `OpenAILlm`. Keep Gemini as a one-line
> fallback. Do not install `litellm`.**

Reasons, in order:

1. **The hackathon supplies OpenAI credits.** A rate-limited or exhausted free-tier
   Gemini key at 03:00 is a missed Game, and README §5 puts uptime above everything.
2. **The native path is strictly better than LiteLlm here.** Same provider, one
   fewer dependency, no `google-adk[extensions]` install, and a much shorter stack
   trace at 04:00. `LiteLlm` earns its keep when you need _many_ providers; we need
   two.
3. **Two providers is the actual resilience story.** `models.py` resolves three
   tier constants. When OpenAI 429s across the board, one env var flips all three
   to Gemini and the graph is unchanged. That is a 10-second incident response,
   and it is worth more than any single-provider optimisation.
4. **`labs` is an unstable namespace** — which is precisely why every model id is
   behind `resolve()`. If `google.adk.labs.openai` moves, one function changes.

### 6.3 Migration cost from SampleRepo's shape

| Step                                                                                                                                                   | Cost                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `pip install openai`                                                                                                                                   | 1 min                               |
| `OPENAI_API_KEY` in env; `_ensure_provider_env()` bridges `.env` → `os.environ` exactly as SampleRepo's `_ensure_gemini_env` does for `GOOGLE_API_KEY` | 5 min                               |
| `settings.MODEL_{FAST,REASONING,VISION}` — three strings                                                                                               | 5 min                               |
| Schema sweep: every optional field to `X \| None`, every numeric bound out of `Field(...)` and into a `field_validator`                                | 20 min                              |
| `test_every_output_schema_survives_a_live_strict_round_trip` (§5.3)                                                                                    | 15 min                              |
| Drop nothing else — we use no `google_search`, no `AgentTool`, no Gemini-only feature                                                                  | 0                                   |
| **Total**                                                                                                                                              | **~45 min, one dev, before Game 1** |

The one thing that would break and is worth naming: SampleRepo's
`grounded_news_agent` uses Gemini's built-in `google_search`, which has no OpenAI
equivalent. We do not use it and must not start — a web search inside a 60-second
window is a latency bet we cannot pay for.

---

## 7. Agents vs algorithms — the boundary, stated plainly

**These must never be an agent, an agent's output field, or a number a model chose:**

| Must be code                                            | Why                                                                                                                                                                                                                                      | Lives in                         |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| **VAT** — the single `× 1.19`                           | `strat-adjuster` §4.0(a): one multiplication, one place, one test. Getting the gross/net convention backwards is a uniform 19 % error and the most likely catastrophic bug in the build. A model applying VAT sometimes is undetectable. | `assemble.py`, one constant      |
| **quantity × unit rate**                                | `QTY` and `UNIT` are printed on the Invoice (F2). Multiplication by a printed number is not a judgement, and a model that multiplies is a model that can multiply wrong.                                                                 | `assemble.py::_framing_mu_sigma` |
| **the gross line total**                                | It is a _consequence_ of qty, unit rate and VAT. Nothing should be able to state it independently, or the three can disagree.                                                                                                            | derived only                     |
| **the log-normal posterior (μ _and_ σ)**                | R4b: width is what determines our score. A model asked for a price returns a point; asked for a price and an interval, it returns a point and a fabricated interval. σ comes from _measured disagreement_ (§3.3).                        | `assemble.py`                    |
| **shrinkage toward the category median (R6b)**          | `τ²/(τ² + σ²)` is empirical Bayes. No language model produces it by reasoning about it.                                                                                                                                                  | `assemble.py` step 5             |
| **the Limit — Q⅓ of the mixture (R4, R6)**              | Pure quantile arithmetic, with a closed form.                                                                                                                                                                                            | `decide.py::limit`               |
| **the Charge — argmax over the 200-point grid (R5b)**   | `a·G(a) + min(a,c)(1−G(a))p(a)`. Microseconds, exact, and R5b's "≈ 0.7 × median" is a _result_ of it, not a rule we hand a model.                                                                                                        | `decide.py::charge`              |
| **the acceptance rate `p(a)` (R5c)**                    | The one that already cost ~60 % of net in simulation. `p = 0` by default; unlocked only by a curve measured from settled Games with enough support. A model must never be able to influence it, directly or by phrasing.                 | `field.py`, R9 only              |
| **the Cap `c` and the `t ≤ c/4` bound**                 | Inverted from published Transactions. Observation, not opinion.                                                                                                                                                                          | `feedback/`                      |
| **the room-perimeter geometry check**                   | `P(r) = 2(√(A·r) + √(A/r))` is a formula (`strat-adjuster` §3.4). The model states the _expected quantity_; the engine does the geometry.                                                                                                | `assemble.py`                    |
| **the small-quantity surcharge and the call-out floor** | `1 + 0.8·max(0, 1 − qty/qty_ref)`. A table and an arithmetic expression.                                                                                                                                                                 | `assemble.py`                    |
| **the double-count haircut**                            | The model _names_ the overlapping index (a reading task); the engine applies the 0.55 factor (an arithmetic one).                                                                                                                        | split, deliberately              |
| **calibration `(β, γ, δ₀, δ₁)`**                        | Maximum likelihood on interval-censored labels. There is no version of this that is a prompt.                                                                                                                                            | `feedback/calibrate.py`          |
| **the ×[0.3, 3.0] Fast-vs-Slow sanity gate**            | It exists precisely to catch a confidently wrong model. It cannot be evaluated by the thing it is guarding against.                                                                                                                      | `runner.py`                      |

**These must be an agent, and only an agent:**

Reading a Policy and finding the clause that addresses this Line Item. Deciding
whether described damage plausibly causes claimed work. Recognising that
"water-damaged laminate" implies a handling surcharge that "laminate" does not.
Naming the German trade. Knowing that a Bodenleger's net Stundenverrechnungssatz is
nearer 52 €/h than 15 €/h or 300 €/h. Reading a rasterised invoice when the text
layer is gone. Saying whether a photograph shows the same peril as the description.

The line between the two lists is exactly one question: **is the answer determined
by the inputs, or does it require knowing something about the world that is not in
front of us?** Determined ⇒ code. World knowledge ⇒ agent. Every item above sorts
cleanly, and nothing sits on the line.

The one case that _looks_ like it sits on the line, and does not:
`deviation_factor`. It is a number, chosen by a model — but it is a **bounded
multiplier on a sourced band**, clamped to `[0.6, 1.6]` by a validator on our side of
the wire. That is the design's central trick and it is worth naming: the model gets
its genuine strength (reading nuance in wording) while being structurally denied its
genuine weakness (producing an unanchored magnitude). A free-form price has
σ ≈ 0.8–1.2; a sourced band with a ±60 % clamp has σ ≈ 0.30, and `strat-adjuster`
§2.3 prices that difference at roughly **+70 % income**.

---

## 8. The 24-hour build plan

This slots into `INDEX.md`'s **Lead track B — The Estimate**, 2 devs. Call them
**D4a (agents)** and **D4b (engine)**. The other three devs are unchanged: D1 runner,
D2 extractor, D3 knowledge, D5 feedback + story.

### 8.1 The dependency that must be resolved first

```
                    evidence.py  (THE CONTRACT)
                    /     |     \
                   /      |      \
             agents.py  assemble.py  Fast Path
              (D4a)      (D4b)        (D1)
                   \      |
                    \     |
                     graph.py -> runner.py
```

**Hour 0, first 30 minutes, both devs in one room: write `evidence.py` and freeze
it.** Every other file in track B is downstream of it, D1's Fast Path imports it,
and D5's Price Memory schema mirrors it. `strat-adjuster` §5.1 says the same thing
about the `Case`/`LineItem` dataclass; this is the second half of that instruction.
After the freeze, the two devs do not block each other at all, because D4b tests
against hand-written evidence fixtures and never needs an API key.

### 8.2 Hour by hour

| When            | D4a — agents                                                                                                                                                                                                                              | D4b — engine                                                                                                                                                                     |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **12:00–12:30** | _(together)_ `evidence.py` written and frozen. Three hand-written fixture Cases committed.                                                                                                                                                | _(together)_ same                                                                                                                                                                |
| **12:30–13:30** | `models.py` + provider smoke test on **OpenAI**: one `LlmAgent(model=gpt-…, output_schema=PriceReport)` round-trips (§6.3). **This is the single riskiest unknown in track B — resolve it before anything else.**                         | `Posterior`, `quantile`, `survival`, `limit`. Property test on mixture monotonicity.                                                                                             |
| **13:30–14:30** | `price_evidence_agent` × 3 framings + `prompts.py`. Run against case 0 by hand, eyeball the anchors.                                                                                                                                      | `evidence_to_posterior` end to end on fixtures. `charge()` grid. `test_identical_evidence…` green.                                                                               |
| **14:30–15:00** | **Hard gate at 14:45** (`strat-adjuster` §5.2): if the Fast Path is not green, both devs drop this and help D1/D2. **Nothing here matters more than a Submission at 15:00.**                                                              | same                                                                                                                                                                             |
| **15:00**       | **Game 1 — Fast Path only.** No agent is on the critical path.                                                                                                                                                                            |                                                                                                                                                                                  |
| **15:00–16:30** | `graph.py` with the three price framings only. `run_evidence`. Slow Path Submission live behind a flag, with the ×[0.3, 3.0] guard on from the first run.                                                                                 | `apply_memory_prior`, `Calibration` wired to a config file so D5 can move β and γ between Games without a deploy.                                                                |
| **16:30–18:00** | `coverage_agent` × 2 + `verify_quotes`. Live behind a flag. **Kill criterion 2 instrumented on the first Game it runs** (share of `NOT_COVERED` > 40 % ⇒ cap π₀).                                                                         | R6b shrinkage + category priors from D3's KB. Uncovered-item branch (R6c) tested.                                                                                                |
| **18:00–20:00** | `relatedness_agent`. `strip_laundered_anchors`. The blind-retrieval canary (§5.4 mechanism 5).                                                                                                                                            | Hand D5 a `replay(evidence, Calibration) -> Submissions` entry point — this **is** the counterfactual evaluator, and it is worth more than anything else either dev ships today. |
| **20:00–22:00** | `image_agent`, behind a flag, **measured** (kill criterion 3 at 22:00).                                                                                                                                                                   | σ-calibration harness against D5's first R9 brackets; the empirical-coverage plot.                                                                                               |
| **22:00–23:00** | Chaos drill on the graph specifically: kill the provider mid-run; return malformed JSON; return 40 findings for 3 items; return an anchor with a forged `memory_key`; time out every node. **Every one must still produce a Submission.** | same, from the engine side: NaN in a band, a zero quantity, a 10 000-item invoice, π₀ = 1.0 on every item.                                                                       |
| **23:00**       | **Pipeline freeze.** Config only after this.                                                                                                                                                                                              | **Pipeline freeze.**                                                                                                                                                             |
| **00:00–08:00** | Night rota with the rest of the team. No deploys 00:00–06:00 unless a Game is being missed.                                                                                                                                               | Same. Calibration updates are config, and config is allowed.                                                                                                                     |
| **08:00–10:30** | Watch the aggression controller find the morning's `p(a)` on its own. Do not override it.                                                                                                                                                 | Final σ calibration pass.                                                                                                                                                        |
| **10:30**       | **Code freeze.** Pitch material: the evidence packet for one real Case, printed, next to the arithmetic that turned it into a Charge. That single side-by-side **is** the ADR 0001 slide.                                                 | same                                                                                                                                                                             |

### 8.3 What track B needs from the others

| From               | What                                                                                     | Blocking?                                                 |
| ------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **D1 (runner)**    | the Slow Path callback and the per-Line-Item merge, so partial output is never discarded | **Yes** — no Slow Path Submission without it              |
| **D2 (extractor)** | `Case` / `LineItem` with `qty`, `unit` normalised, and a **correct index**               | **Yes**, and the index is the one that costs a whole Game |
| **D3 (knowledge)** | `kb_id`, the reference band, `sigma_log`, `qty_ref`, `overlaps`                          | No — `kb_band=None` degrades to the framings' own bands   |
| **D5 (feedback)**  | `Calibration` after each settled Game; Price Memory rows with `n_games`                  | No — cold-start defaults ship in the dataclass            |

Only two hard blocks, both on things D1 and D2 are building anyway for the Fast Path.
That is the point of putting the engine behind a frozen contract.

---

## 9. Kill criteria and honest downside

### 9.1 Kill criteria — each with a time, a metric, a threshold, an action

These are **additional** to `strat-adjuster` §7.1 (which owns the VAT check, the
coverage-hallucination cap, the image kill and the σ-coverage loop). These are the
ones this document's own design creates.

| #      | When                  | Metric                                                                    | Threshold                              | Action                                                                                                                                                                                                                                                                                                             |
| ------ | --------------------- | ------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A1** | Sat 13:30             | OpenAI strict `output_schema` round-trip on all five schemas              | any failure                            | Flip `models.py` to Gemini for that tier. If both fail: **drop `output_schema`, use `response_mime_type=application/json` + our own parse**, which SampleRepo's `_parse_structured` already does.                                                                                                                  |
| **A2** | every Game            | Slow Path p95 wall clock                                                  | > 24 s                                 | Drop the image node, then the third price framing. Two framings still give an `s_between`.                                                                                                                                                                                                                         |
| **A3** | Sat 18:00 (~14 Games) | `s_between` across the three price framings, median                       | < 0.05                                 | **The framings are not different estimators** — they are one estimator asked three times, and σ is a lie. Replace `einkaeufer` with the `komparator` framing (price _relative_ to three retrieved anchors), which is genuinely different. If still < 0.05, raise `sigma_floor` to 0.30 and say so in the write-up. |
| **A4** | Sat 20:00             | share of anchors dropped by `strip_laundered_anchors`                     | > 5 %                                  | The prompt's provenance rule is not landing. Stop injecting the Price Memory into the price prompt entirely; apply it engine-side only (`apply_memory_prior`), which costs the F6 effect but removes the laundering path completely.                                                                               |
| **A5** | Sun 02:00             | blind-retrieval canary: `\|μ_blind − μ_retrieved\|` vs what `n` justifies | agreement 2× tighter than `n` warrants | Same action as A4.                                                                                                                                                                                                                                                                                                 |
| **A6** | Sat 22:00             | Games where the ×[0.3, 3.0] guard rejected the Slow Path                  | > 15 %                                 | The pipeline is confidently wrong at a rate that makes it net-negative. **Turn the Slow Path off** and run Fast Path only for the night. It is a better night than a broken one.                                                                                                                                   |
| **A7** | any time              | a Submission that is not reproducible from its stored evidence            | any                                    | Stop. This is ADR 0001's central claim failing, and it means something non-pure crept into `assemble.py` or `decide.py`. Fifteen-minute fix, and everything downstream depends on it.                                                                                                                              |

### 9.2 Honest downside

**D1 — More moving parts under a 60-second budget.** ADR 0001 says it plainly:
"four agents plus a join plus an engine is more to go wrong than one call." We have
made it _seven_ agents plus a join. The mitigation is real but it is not free — the
Fast Path pays for it, and the ×[0.3, 3.0] guard makes the Slow Path
non-decreasing in quality. But every one of those seven is a chance to spend 10
seconds and learn nothing. **If it comes to it, the ordering in which we shed them
is fixed and written down** (A2): image, then `einkaeufer`, then `coverage_charitable`,
then `kalkulator`. Coverage-strict and `sachverstaendiger` are the last two standing,
because `t = 0` outranks everything and one price framing beats none.

**D2 — σ from framing disagreement may be measuring the wrong thing.** Three
framings of the same model share training data. Correlated error is invisible to
between-framing variance, and the whole §3.3 construction would then produce a
confident, narrow, _wrong_ posterior — exactly the poisoning ADR 0001 warns about,
arrived at by a more sophisticated route. `sigma_floor = 0.18` is the guard,
`γ₀ = 2.0` errs wide by design, and A3 is the detector. But if the true σ floor is
0.45 because the _generator_ is noisy (`strat-adjuster` risk 1), no amount of this
helps and we capture ~48 % rather than ~64 % of attainable income. We should put
that in the write-up ourselves rather than let QuantCo find it.

**D3 — The anchors may be reverse-engineered.** `iota` is the cleverest term in §3.3
and it depends on the model building its anchors _before_ stating its band. A model
that states a band and then back-fills a build-up to match produces `iota ≈ 0` and
silently deletes a σ term. `ANCHOR_CONTRACT` says not to; that is a prompt, and
prompts are not guarantees. The detector is A3, and the honest fallback is to treat
`iota` as diagnostic only and lean entirely on `s_between`.

**D4 — `google.adk.labs` is an unstable namespace.** We are betting a tournament on
a module whose own package path says "labs". The mitigation is that every model id
is behind `resolve()` and the fallback is a single env var — but if `OpenAILlm`'s
schema handling has a bug we hit at 03:00, we will be debugging someone else's alpha
code with a Game every 12 minutes 37 seconds. A1 at 13:30 is what buys down this
risk, and it is scheduled first for exactly that reason.

**D5 — The evidence contract could be wrong in a way we cannot see.** We froze it in
the first 30 minutes on the basis of one sample invoice and a slide. If real Cases
carry something the schema cannot express — a per-invoice sub-limit, an item that is
partially covered, a quantity range rather than a quantity — the schema silently
drops it and no test fails, because our tests assert _consistency_, not
_completeness_. Mitigation: every gate's raw JSON is stored alongside the parsed
evidence from Game 1, so a schema gap is recoverable after the fact rather than lost.
It costs a few hundred kilobytes a Game and it is the cheapest insurance in the plan.

**What would make us abandon this design.** A6: if the ×[0.3, 3.0] guard is
rejecting the Slow Path on more than 15 % of Games by Saturday night, the agent team
is not producing evidence that improves on the Fast Path's KB lookup, and the honest
move is to run Fast-Path-only overnight and spend Sunday morning on calibration
instead. Note what survives even then: `evidence.py`, `assemble.py` and `decide.py`
are untouched by that decision — the Fast Path already constructs a `LineItemEvidence`
with `price=[]` and `coverage=[]` and prices it through the same engine. **There is
no version of this plan where the engine is thrown away**, and that asymmetry — the
agents are optional, the engine is not — is exactly what ADR 0001 decided, and the
best single argument that the decision was right.
