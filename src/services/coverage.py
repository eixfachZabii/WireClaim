"""Per-Line-Item coverage probability -- "does the Policy indemnify this position at all?"

This replaces the binary gate in `services/fraud_detection.py`. The reason it is a
probability and not a boolean is arithmetic, not taste:

The Limit is the bottom-third quantile of the posterior over `t` (`src/pricing.py`), and
a coverage doubt enters that posterior as probability mass at zero. Below
`p_covered = 1/3` the bottom third *is* zero, so the Limit collapses on its own, with no
threshold anywhere in the code. A boolean destroys exactly the middle of that range --
0.4 to 0.8 -- which is the only region where the decision is live. Game 17 is the proof
in the other direction: a bug floored every coverage probability at 0.9, the Limit could
never collapse, and we paid in full on the 40% of positions that are worth nothing.

## What this module decides, and what it must not touch

* It decides `p_covered` = P(the Policy indemnifies this position at all), i.e. P(t > 0).
  It does **not** decide whether the price is inflated; that is the pricing engine's job.
* It never lowers the Charge. An uncovered item has `t = 0`, so a rejected Charge costs
  nothing -- charging is a free option (README R6c, Game 3).
* It never blocks or fails the submission. Every error path returns defaults, and
  `assess_coverage` does not raise.

## Why there is no global prior

Measured over the 192 settled Line Items, 76 are worth exactly zero -- but the share per
Case runs from **0% (Case 12) to 67% (Case 10)**. A detector that always finds something
is wrong on a whole Case at a time. So the prompt is told explicitly that a Case may have
no uncovered items at all, the default when nothing is found is 0.9, and nothing in this
module renormalises towards a target rate.

## The three failure modes the prompt is written against

1. **Judge the billed SERVICE, not the object.** Case 8 POS 4: the robot vacuum itself is
   not indemnified, but §7.1.7(i) pays for its *inspection* "even where the property
   investigated turns out not to be indemnified". Case 12 POS 2 repeats it with a washing
   machine (§7.1.7(e)).
2. **Cross-references restore cover.** An exclusion closing with "the head of cost under
   5.2.6 remains unaffected" is a pointer, not an exclusion -- Case 12 excludes works of
   art and then indemnifies their restoration through §5.2.6.
3. **A suspicious detail in the Damage Description is not an exclusion.** Case 7 dangles
   an air-conditioning unit "a couple of metres from the hob" while the Policy says
   proximity to another appliance does not remove cover. Only a Policy clause counts,
   which is why a low probability without a verified quote is pulled back up.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Sequence

from src.api import get_llm_client, get_model_name
from src.data.models import CaseData, LineItem
from src.policy_quote import is_policy_quote, normalize
from src.policy_slice import slice_policy
from src.timing import log_timing, start_timer

logger = logging.getLogger(__name__)

#: Default when the model finds nothing, or when anything at all goes wrong. Coverage is
#: the normal case and over-flagging costs twice: we forfeit the Charge on a covered item
#: and then fund the field on the same item through the 1.5a wrongful-rejection penalty.
DEFAULT_P_COVERED = 0.9

#: Below this the bottom-third quantile of the posterior is zero, so this is the value at
#: which a verdict actually starts to move money. Named here so the tests and the
#: calibration read the same constant as `src.pricing.COVERAGE_FLOOR`.
LIMIT_COLLAPSE = 1.0 / 3.0

#: An unquoted doubt is still information -- the model is right more often than not -- but
#: it is not proof, and Case 7 shows the Damage Description manufacturing false doubt. So
#: an unverified verdict is shrunk towards the default instead of being either trusted or
#: thrown away. At 0.5 a model saying 0.05 lands at ~0.48, above the collapse point, so no
#: Limit is zeroed on a story alone.
UNVERIFIED_SHRINK = 0.5

#: `quantity_missing` is the dash printed in the amount and unit columns. 20 of 20 such
#: positions in the settled Games are worth exactly zero, against a 40% base rate, so a
#: Laplace-smoothed P(t = 0 | dash) is 21/22 = 95%. This is the one signal strong enough
#: to override the model in both directions: it caps `p_covered` whatever the model says.
#:
#: The ceiling is set above the 0.045 the count implies, on purpose. It is 20 observations
#: from 6 Cases and one parser; a mislabelled dash must cost us a shaded Limit, not a
#: guaranteed wrongful rejection. Sweeping 0.30 / 0.20 / 0.10 over the settled record moved
#: recall not at all and the Brier score by 0.004, so the cautious end is free.
QUANTITY_MISSING_CEILING = 0.10

#: The printed invoice is context, not the payload; a page of headers is ~2k characters
#: and the biggest settled Case runs to five pages. Truncation keeps a pathological PDF
#: from crowding out the Policy.
MAX_INVOICE_CHARS = 12000

#: Independent samples per chunk, averaged. The model's per-Case verdicts are noisy -- two
#: runs of the identical prompt over the settled record scored 68.4%/5.2% and 72.4%/6.0%
#: (recall of true-zero items / covered items wrongly pushed under 1/3) -- and the noise is
#: not symmetric in cost: a false positive forfeits guaranteed income and then pays the
#: field 1.5a on the same Line Item.
#:
#: Averaging is the cheapest fix available, because the disagreements are exactly the
#: doubtful items and the mean lands them in the middle band the Limit is built to read.
#: Measured over Games 1-14: single runs 68.4/5.2/0.131 and 72.4/6.0/0.129
#: (recall/false-positive/Brier), their mean 67.1/1.7/0.116. The false-positive rate falls
#: by two thirds for four points of recall, and the Brier score improves as well.
#:
#: Two, not three: a third sample moved the pooled numbers to 65.8/4.3/0.118, inside the
#: run-to-run noise, for another 50% of tokens. The samples run concurrently, so this costs
#: tokens and not wall clock.
SAMPLES = 2

#: Items per LLM call. One call per Case would let a single failure blind a 39-item
#: invoice; one call per item repeats a ~20k-character Policy 39 times and loses the
#: cross-item view that keeps the model from flagging a uniform Case. Chunks give both
#: parallelism and independent failure.
CHUNK_SIZE = 8

#: Per-call ceiling. `assess_coverage` also honours the Game deadline when it is given.
COVERAGE_TIMEOUT_SECONDS = 40.0

#: Never let the coverage pass eat the submission window.
SUBMISSION_RESERVE_SECONDS = 5.0


@dataclass(frozen=True)
class CoverageVerdict:
    """One coverage judgement, in the form `src.pricing.Evidence` can consume."""

    index: int
    """The POS number printed on the invoice, gaps preserved. Case 11 has no POS 12 and
    the tournament has no index 12 for that Game, so never renumber by row ordinal."""

    p_covered: float
    """0..1, the probability the Policy indemnifies this position at all (P(t > 0))."""

    clause: str
    """The supporting Policy sentence, verbatim."""

    quote_verified: bool
    """Whether `src.policy_quote.is_policy_quote` accepted `clause` against the Policy."""

    reasoning: str = ""

    @property
    def collapses_limit(self) -> bool:
        """True when this verdict alone drives the Limit to zero."""
        return self.p_covered <= LIMIT_COLLAPSE

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "p_covered": self.p_covered,
            "clause": self.clause,
            "quote_verified": self.quote_verified,
            "reasoning": self.reasoning,
        }


SYSTEM_PROMPT = """You are an insurance coverage examiner. For each invoice Line Item, output the probability that the Policy indemnifies that position AT ALL.

You are NOT judging whether the price is too high. Price is somebody else's job. You judge only: if this position were priced perfectly fairly, would the Policy pay anything for it, or exactly zero?

Output `p_covered` in [0, 1]:
  1.00-0.85  the Policy plainly indemnifies this head of cost
  0.85-0.50  a clause raises a real doubt but does not settle it
  0.50-0.34  probably not indemnified, but the clause is not decisive
  0.33-0.00  an exclusion or a scope limit in the Policy settles it: this position is worth zero
Below 0.34 the position is treated as worth nothing, so put a value there only when you can quote the clause that proves it.

HOW TO DECIDE

1. Judge the BILLED SERVICE, not the object it concerns. The Line Item is a head of cost, not a thing. Investigation, leak detection, drying, assessment, expert reports, disposal, making-good, and recovery, salvage, securing and emergency measures are frequently indemnified in their own right EVEN WHERE THE OBJECT CONCERNED IS NOT INSURED - many policies say exactly that, in terms. An uninsured appliance whose *inspection* is billed is a COVERED Line Item, and a locksmith called out to release a recovered but uninsured object is a COVERED Line Item, while the repair of that same object is not. Look for the clause that indemnifies the service before you reject it because of the object.

2. Read cross-references to the end. An exclusion that closes with "the head of cost under 5.2.6 remains unaffected", "without prejudice to", "save as provided in", "this does not apply to" or any other pointer to another clause is a POINTER, NOT AN EXCLUSION. Before you say "not covered", find the referenced clause number in the Policy text and read whether it restores cover. If it does, the position is covered.

3. Only the POLICY can exclude. A suspicious, careless or unlucky detail in the Damage Description is not an exclusion. Proximity to a heat source, an old appliance, a self-installed part, a missing receipt - none of these remove cover unless a Policy clause says so. If your reason lives in the description rather than in a quotable clause, `p_covered` stays high.

4. A LIMIT ON THE AMOUNT IS NOT AN EXCLUSION. This is the single most expensive mistake you can make. A deductible, a sub-limit, an "up to [amount]" ceiling, depreciation, a new-for-old restriction, and above all "no improvement on the pre-loss standard" / betterment all REDUCE what is paid. They do not make the position worth zero. A premium solid-oak replacement for a damaged table, or premium hardwood skirting where softwood was destroyed, is a COVERED position that will be paid down to the pre-loss standard: `p_covered` stays at 0.8 or above. The one exception is a line that bills ONLY the difference - "Upgrade to natural stone floor", "surcharge for premium finish" - which is the uninsured part on its own and is worth zero.

5. READ THE PROVISO. Exclusions carry qualifiers: "save where", "save within 7.1.7(g)", "except where", "unless", "other than", "this does not apply to". The proviso is part of the rule. If the position could plausibly fall inside the saved subset, cover survives and `p_covered` stays at 0.5 or above. Only when the position is clearly outside the proviso does it drop below 0.34.

6. LABOUR AND ATTENDANCE FOLLOW THE WORK. Skilled hours, apprentice hours, call-out, vehicle and travel charges, assembly and materials consumed are indemnified as part of the work they were spent on - if that work is indemnifiable. They are worth zero when the underlying work is not indemnifiable, or when the Policy says only the first such charge is paid and this is a repeat. Exclusions aimed at "the contractor's own business operation" target the trade's own tools, plant, software, licences and administrative overhead, NOT the hours actually worked on this repair.

7. THE DEVICE IS NOT THE WORK. A line that bills a PIECE OF EQUIPMENT as such - "Condensation dryer", "Drying fan", "Room dryer unit", hand tools, plant, small equipment - is usually caught by the "own tools, plant and consumable small equipment as such" exclusion even though the drying or the repair carried out with it is fully indemnified. Go and read that clause before you pass such a line: if the Policy separately indemnifies the HIRE or RENTAL of drying plant, the line is covered; if it only indemnifies the drying measure, the equipment line is worth zero. This distinction decided six invoices in the settled record.

8. IS THE PROPERTY EVEN INSURED? Before judging the head of cost, check the list of insured property and insured locations (usually PART 4, and any "property not insured" list). Work on an object or an installation that falls outside it - a means of transport, an outbuilding, a swimming pool and its pipework, property belonging to someone else - is worth zero however ordinary the trade and however genuine the peril: the labour, the materials and the attendance on that work all go with it. This is the mirror image of rule 1: rule 1 rescues a SERVICE that the Policy names in its own right (investigation, assessment, leak detection), while this rule zeroes ordinary repair work performed on an uninsured object.

9. DUPLICATES: where the Policy indemnifies only the first charge for the same head of cost, the FIRST occurrence on the invoice keeps its cover and the later repeats of the same head - "return visit", "already billed by", a second identical line - are the ones worth zero. Do not zero the whole group.

10. There is no quota. The share of worthless positions per invoice ranges from 0% to 67% in the measured record. Many invoices contain NOTHING excluded; some contain a majority. Judge each position on its own clause. Never flag a position because it "feels like" the invoice should contain some. If you have found nothing for a position, return 0.9.

11. Use the middle of the scale when you are genuinely torn. Below 0.34 means the position gets NOTHING AT ALL. If your only reason would shrink the amount rather than remove it (rule 4), the answer is 0.8 or above, not a low number. If a clause plainly catches the position but you cannot rule out a proviso or a restoring cross-reference, 0.4-0.6 is the honest answer and it is read downstream as a real probability, not as a shrug.

12. `quantity_missing: true` means the invoice printed a dash instead of an amount and a unit for that position. Every one of the 20 such positions in the settled record was worth exactly zero. Treat it as strong evidence, and still cite the clause that says so.

13. If a section titled "LOSS DESCRIPTION AND OPERATIVE PROVISIONS FOR THIS CLAIM" is present, it enumerates the clauses that decide this very claim. Use it first.

THE QUOTE - a verdict below 0.34 is DISCARDED unless the quote passes an automatic check

`clause` is checked by a program, not by a human. The check is literal and it has three conditions, all of which must hold, or your verdict is thrown away and the position is paid in full:

  (a) VERBATIM. The text must appear in the Policy above as one CONTIGUOUS run of characters. Copy it, do not retype it. No ellipsis, no "[...]", no paraphrase, no summary, no joining of two passages that are not adjacent, no correcting of spelling or punctuation. Line breaks and indentation inside the span are fine - only the words are compared.
  (b) AT LEAST 60 CHARACTERS.
  (c) THE QUOTED SPAN ITSELF must contain wording that says something is not paid: "not covered", "not indemnified", "excluded", "does not cover", "does not extend", "no indemnity", "shall not", "no cover", "not reimbursed".

Condition (c) is the one that fails most often, and here is why. Policies list exclusions as a lead-in sentence followed by lettered sub-paragraphs:

    7.1.8 Outlay that is not an indemnity for property
    The following are not indemnified, however they may be described [...]:
      (a) measures directed at the general condition [...];
      (b) carriage, freight, delivery, dispatch, packaging, postage [...];

Quoting only "(b) carriage, freight, delivery..." FAILS: that fragment nowhere says it is not paid. You must start the quote at the lead-in that carries the exclusionary words and run UNBROKEN to the end of the sub-paragraph you rely on - copying every intervening sub-paragraph as well, even if that makes the quote long. Long is fine. There is no upper length limit.

For a high `p_covered` the quote is not checked: give the clause that grants the cover, or leave it empty.

BEFORE YOU RETURN a `p_covered` below 0.34, re-read your own `clause` and confirm all three conditions. If you cannot produce a passing quote, you may still return the low number, but say so in `reasoning`.

Return one entry per Line Item given to you, using the same `index` values."""


RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "coverage_assessment",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "index": {"type": "integer"},
                        "p_covered": {"type": "number"},
                        "clause": {"type": "string"},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["index", "p_covered", "clause", "reasoning"],
                },
            }
        },
        "required": ["items"],
    },
}


#: How far back a repaired quote may reach for the sentence that carries the exclusion.
#: A list exclusion ("The following are not indemnified: (a) ... (b) ...") puts the words
#: that fail `is_policy_quote` in the lead-in, sometimes two sub-paragraphs above the one
#: the model cited, and the longest such gap measured over the 14 policies is ~1,600
#: characters. Beyond that the window stops being about the cited clause.
QUOTE_REPAIR_LOOKBACK = (0, 150, 300, 600, 1200, 2000)

#: A citation shorter than this is not specific enough to anchor a repair.
MIN_ANCHOR_WORDS = 6


def _clamp(value: Any, default: float = DEFAULT_P_COVERED) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return min(max(number, 0.0), 1.0)


def default_verdict(line_item: LineItem) -> CoverageVerdict:
    """What we say about a Line Item we could not assess. Coverage is the normal case."""
    return CoverageVerdict(
        index=line_item.index,
        p_covered=DEFAULT_P_COVERED,
        clause="",
        quote_verified=False,
        reasoning="No coverage assessment available; defaulting to covered.",
    )


def _longest_anchor(quote: str, policy_text: str) -> list[str]:
    """The longest run of words from `quote` that occurs verbatim in the Policy.

    Measured over the settled Cases, the model's citation is almost never invented -- it
    is *assembled*. It prefixes a sub-paragraph with its clause number ("7.1.8 (d) call-out,
    travel, ...") although the number sits two paragraphs above, or it welds a lead-in onto
    sub-paragraph (b) while skipping (a). Both produce a string that is nowhere in the
    Policy while pointing squarely at real text, so the run that *does* match is a reliable
    anchor for finding what the model meant.
    """
    words = normalize(quote).split()
    policy = normalize(policy_text)
    best: list[str] = []
    for start in range(len(words)):
        length = len(best) + 1
        if start + length > len(words):
            break
        if " ".join(words[start : start + length]) not in policy:
            continue
        while start + length < len(words) and " ".join(words[start : start + length + 1]) in policy:
            length += 1
        best = words[start : start + length]
    return best


def _anchor_span(anchor: Sequence[str], policy_text: str) -> tuple[int, int] | None:
    """Where the anchor sits in the *original* Policy text, tolerating line wrapping."""
    if len(anchor) < MIN_ANCHOR_WORDS:
        return None
    pattern = re.compile(r"\s+".join(re.escape(word) for word in anchor), re.IGNORECASE)
    match = pattern.search(policy_text)
    return (match.start(), match.end()) if match else None


def repair_quote(clause: str, policy_text: str) -> str:
    """Return a quote that `is_policy_quote` accepts, or "" if none can be built.

    The gate in `src.policy_quote` is deliberately unforgiving and we do not touch it --
    it decides whether a Limit goes to zero. What we can do is stop throwing away correct
    verdicts over citation *formatting*: anchor on the longest run of the model's quote
    that really is in the Policy, then widen the span backwards through the actual Policy
    text until the exclusionary lead-in is inside it, and hand *that* to the same gate.

    Everything returned is a contiguous verbatim slice of `policy_text`; nothing is
    synthesised. If no window up to `QUOTE_REPAIR_LOOKBACK[-1]` characters back passes,
    the quote stays rejected.
    """
    if not clause or not policy_text:
        return ""
    if is_policy_quote(clause, policy_text):
        return clause
    span = _anchor_span(_longest_anchor(clause, policy_text), policy_text)
    if span is None:
        return ""
    start, end = span
    for lookback in QUOTE_REPAIR_LOOKBACK:
        begin = max(start - lookback, 0)
        if begin and (newline := policy_text.find("\n", begin, start)) >= 0:
            begin = newline + 1  # start on a line boundary, never mid-word
        candidate = policy_text[begin:end]
        if is_policy_quote(candidate, policy_text):
            return candidate
    return ""


def calibrate(
    raw_p: float,
    clause: str,
    policy_text: str,
    *,
    quantity_missing: bool = False,
) -> tuple[float, bool, str]:
    """Turn a raw model probability plus its quote into the probability we act on.

    The model's number is evidence, the quote is proof, and the two are combined rather
    than one overriding the other:

    * `quantity_missing` overrides everything, in both directions. It is the only signal
      measured at 20 out of 20, and on the settled record the model talks itself out of
      four of those positions with a plausible story about the work being indemnifiable.
    * A verdict above the collapse point is otherwise taken as given -- it costs nothing.
    * A verdict below it that carries a verified (or repairable) Policy quote stands.
    * A verdict below it with no usable quote is shrunk towards the default. This is the
      Case 7 guard: the Damage Description manufactures doubt that no clause supports, and
      an unquoted doubt must not zero a Limit on its own.

    Returns `(p_covered, quote_verified, clause)`, where `clause` is the model's quote
    when the gate accepted it and the repaired verbatim Policy span when it did not.
    """
    probability = _clamp(raw_p)
    if probability > LIMIT_COLLAPSE and not quantity_missing:
        # Nothing is at stake above the collapse point, so do not spend the repair.
        return probability, is_policy_quote(clause, policy_text), clause
    repaired = repair_quote(clause, policy_text)
    if quantity_missing:
        return min(probability, QUANTITY_MISSING_CEILING), bool(repaired), repaired or clause
    if repaired:
        return probability, True, repaired
    return DEFAULT_P_COVERED - UNVERIFIED_SHRINK * (DEFAULT_P_COVERED - probability), False, clause


@lru_cache(maxsize=32)
def _read_invoice_text(invoice_path: str) -> str:
    """The printed invoice, best effort. Never raises, never blocks on failure.

    `LineItem` carries a name and a quantity and nothing else, and that loses the header.
    Case 14 is one PDF holding *two* invoices: a bicycle service (POS 1-8, on an uninsured
    means of transport, all worth zero) and a locksmith (POS 9-13, called out to cut the
    lock so the recovered bicycle could be released -- indemnified, and three of those five
    positions are worth real money). Seen as one flat list of names, POS 9-13 look like a
    duplicate billing of POS 4-8 and the whole invoice reads as uncovered. The header is
    the only thing that distinguishes them, so it goes in the prompt.
    """
    try:
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(invoice_path).pages)
    except Exception as error:  # pragma: no cover - depends on the extracted Case
        logger.info("Invoice text unavailable for %s: %s", invoice_path, error)
        return ""
    return text[:MAX_INVOICE_CHARS]


def invoice_text(case: CaseData) -> str:
    try:
        return _read_invoice_text(str(case.case_dir / "invoices.pdf"))
    except Exception:  # pragma: no cover - defence in depth
        return ""


def build_prompt(case: CaseData, line_items: Sequence[LineItem], policy_text: str) -> str:
    printed = invoice_text(case)
    printed_block = (
        "=== THE INVOICE AS PRINTED ===\n"
        "This file may hold SEVERAL invoices from different trades. A position belongs to "
        "the invoice it is printed under; judge it against that provider's work, and do not "
        "read the same position number twice.\n"
        f"{printed}\n\n"
        if printed
        else ""
    )
    return (
        f"=== POLICY (sliced to the operative parts) ===\n{policy_text}\n\n"
        f"=== DAMAGE DESCRIPTION ===\n{case.description_text}\n\n"
        f"{printed_block}"
        "=== INVOICE LINE ITEMS TO ASSESS ===\n"
        f"{json.dumps([item.to_dict() for item in line_items], ensure_ascii=False, indent=1)}\n\n"
        f"Return exactly {len(line_items)} entries, one per index above."
    )


def _assess_chunk(
    case: CaseData,
    line_items: Sequence[LineItem],
    policy_text: str,
    timeout: float,
) -> tuple[CoverageVerdict, ...]:
    response = get_llm_client().chat.completions.create(
        model=get_model_name(),
        timeout=timeout,
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(case, line_items, policy_text)},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    return _verdicts_from_payload(payload, line_items, case.policy_text)


def _verdicts_from_payload(
    payload: Any,
    line_items: Sequence[LineItem],
    policy_text: str,
) -> tuple[CoverageVerdict, ...]:
    """Map a model payload onto the requested indices, defaulting anything it skipped."""
    entries: dict[int, dict[str, Any]] = {}
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    for entry in raw_items or ():
        if not isinstance(entry, dict):
            continue
        try:
            entries[int(entry.get("index"))] = entry
        except (TypeError, ValueError):
            continue

    verdicts: list[CoverageVerdict] = []
    for line_item in line_items:
        entry = entries.get(line_item.index)
        if entry is None:
            verdicts.append(default_verdict(line_item))
            continue
        probability, verified, clause = calibrate(
            entry.get("p_covered"),
            str(entry.get("clause") or ""),
            policy_text,
            quantity_missing=line_item.quantity_missing,
        )
        verdicts.append(
            CoverageVerdict(
                index=line_item.index,
                p_covered=probability,
                clause=clause,
                quote_verified=verified,
                reasoning=str(entry.get("reasoning") or ""),
            )
        )
    return tuple(verdicts)


def _chunks(line_items: Sequence[LineItem], size: int = CHUNK_SIZE) -> list[tuple[LineItem, ...]]:
    return [tuple(line_items[start : start + size]) for start in range(0, len(line_items), size)]


def _remaining_seconds(deadline: float | None) -> float:
    if deadline is None:
        return COVERAGE_TIMEOUT_SECONDS
    try:
        now = asyncio.get_running_loop().time()
    except RuntimeError:  # pragma: no cover - only outside a loop
        return COVERAGE_TIMEOUT_SECONDS
    return max(min(COVERAGE_TIMEOUT_SECONDS, deadline - now - SUBMISSION_RESERVE_SECONDS), 1.0)


async def _timed_chunk(
    case: CaseData,
    line_items: Sequence[LineItem],
    policy_text: str,
    timeout: float,
) -> tuple[CoverageVerdict, ...]:
    started_at = start_timer()
    try:
        verdicts = await asyncio.wait_for(
            asyncio.to_thread(_assess_chunk, case, line_items, policy_text, timeout),
            timeout=timeout,
        )
    except Exception as error:
        log_timing(
            logger, "coverage_chunk", started_at, "failed",
            game=case.game_id, first_index=line_items[0].index if line_items else None,
        )
        logger.warning("Coverage chunk failed for Game %s: %s", case.game_id, error)
        return tuple(default_verdict(item) for item in line_items)
    log_timing(
        logger, "coverage_chunk", started_at,
        game=case.game_id, items=len(line_items),
        collapsed=sum(1 for verdict in verdicts if verdict.collapses_limit),
    )
    return verdicts


def merge_samples(samples: Sequence[CoverageVerdict]) -> CoverageVerdict:
    """Average independent verdicts on one Line Item and keep the best-evidenced clause.

    The probability is the plain mean -- two samples that disagree describe a genuinely
    doubtful position, and the middle band is what the Limit is built to read. The clause
    comes from the most incriminating sample that carries a verified quote, so an item
    that survives the average still ships the exclusion someone found.
    """
    probability = sum(sample.p_covered for sample in samples) / len(samples)
    verified = [sample for sample in samples if sample.quote_verified]
    evidence = min(verified or list(samples), key=lambda sample: sample.p_covered)
    return CoverageVerdict(
        index=evidence.index,
        p_covered=probability,
        clause=evidence.clause,
        quote_verified=evidence.quote_verified,
        reasoning=evidence.reasoning,
    )


async def assess_coverage(
    case: CaseData,
    deadline: float | None = None,
) -> tuple[CoverageVerdict, ...]:
    """A coverage probability for every Line Item of `case`, in invoice order.

    Never raises and never blocks the submission: a failed chunk degrades to
    `DEFAULT_P_COVERED` for its own items only, and a Case with no Line Items -- or an
    unexpected failure of the whole pass -- yields an empty tuple.
    """
    started_at = start_timer()
    if not case.line_items:
        return ()
    chunks = _chunks(case.line_items)
    try:
        policy_text = slice_policy(case.policy_text)
        timeout = _remaining_seconds(deadline)
        results = await asyncio.gather(
            *(
                _timed_chunk(case, chunk, policy_text, timeout)
                for _ in range(SAMPLES)
                for chunk in chunks
            ),
            return_exceptions=True,
        )
    except Exception as error:  # pragma: no cover - defence in depth, must never raise
        logger.error("Coverage assessment failed for Game %s: %s", case.game_id, error)
        return tuple(default_verdict(item) for item in case.line_items)

    samples: dict[int, list[CoverageVerdict]] = {}
    for chunk, result in zip(chunks * SAMPLES, results):
        if isinstance(result, BaseException):
            logger.warning("Coverage chunk raised for Game %s: %s", case.game_id, result)
            result = tuple(default_verdict(item) for item in chunk)
        for verdict in result:
            samples.setdefault(verdict.index, []).append(verdict)
    verdicts = {index: merge_samples(group) for index, group in samples.items() if group}

    ordered = tuple(
        verdicts.get(item.index) or default_verdict(item) for item in case.line_items
    )
    log_timing(
        logger, "coverage", started_at,
        game=case.game_id, items=len(ordered),
        collapsed=sum(1 for verdict in ordered if verdict.collapses_limit),
    )
    return ordered


def coverage_probabilities(verdicts: Iterable[CoverageVerdict]) -> dict[int, float]:
    """`{index: p_covered}`, the shape `src.pricing.Evidence` wants."""
    return {verdict.index: verdict.p_covered for verdict in verdicts}
