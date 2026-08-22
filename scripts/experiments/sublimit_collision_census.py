"""How often does an aggregate class sub-limit collide within one Case?

Coordinator's lead (Game 44): Case 44's policy S4.2.2 puts every "Valuables" item (jewellery,
watches, precious metals) into ONE aggregate sub-limit per insured event. When a Case invoices
several such items, the pot can be exhausted by the most expensive one, leaving the others
worth 0 -- even though nothing about the *other* items is individually excluded. Game 41's
watch (t >= 11,131, same S4.2.2 clause) is the same shape on a single-item Case (so it cannot
show the collision, only the level miss it causes elsewhere).

This is a pure Fair-Value-bracket analysis. No LLM calls, no policy parsing beyond a keyword
match on the invoice Line Item's own wording -- the class the coordinator named (valuables:
watches, rings, necklaces, bracelets, earrings, jewellery, precious metals/stones) is
detected directly from the printed item name, which is how a Reviewer would have to detect it
live anyway (the policy clause has to be re-quoted per Case, but the CLASS a Line Item belongs
to is nameable from the invoice alone).

"Settles positive" / "settles ~0" uses the exact convention already used everywhere else in
this codebase (`GameSnapshot.zero_fair_value`): t_lo == 0 means no team was ever wrongfully
rejected on that item, i.e. entitlement was never demonstrated -- t = 0 is the only
observable signature of "worthless" from settled Transactions.

    PYTHONPATH=. pixi run python scripts/experiments/sublimit_collision_census.py --games 1-44
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from invert_fair_values import brackets  # noqa: E402
from pull_transactions import teams  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.data.case_loader import read_case  # noqa: E402

import asyncio  # noqa: E402

CASES = Path("[PUBLIC] EHL Cases/cases")

# The class the coordinator named directly: S4.2.2 "Valuables" -- jewellery, watches,
# adornments of precious metal / set with precious stones.
VALUABLES_RE = re.compile(
    r"\b(watch(?:es)?|ring|necklace|bracelet|earring|jewell?ery|brooch|cufflink|pendant|"
    r"tiara|gem(?:stone)?|diamond|locket|anklet)\b",
    re.IGNORECASE,
)

# A broader, secondary net: ANY "compensation for [a discrete physical object]" line, not
# just valuables -- catches other aggregate classes the policy might name (electronics,
# means-of-payment, garden equipment, ...) that this task's brief did not point at by name.
GENERIC_OBJECT_RE = re.compile(
    r"\b(watch(?:es)?|ring|necklace|bracelet|earring|jewell?ery|brooch|cufflink|pendant|"
    r"tiara|gem(?:stone)?|diamond|locket|anklet|"
    r"phone|laptop|tablet|camera|bicycle|bike|television|tv|speaker|"
    r"cash|banknotes?|currency|"
    r"handbag|bag|wallet|purse|suitcase|luggage)\b",
    re.IGNORECASE,
)


def case_line_items(game_id: int):
    case_dir = CASES / f"case_{game_id:02d}"
    if not (case_dir / "policy.txt").exists():
        return None
    case = asyncio.run(read_case(game_id, case_dir))
    return case.line_items


def class_of(name: str, pattern: re.Pattern) -> str | None:
    m = pattern.search(name)
    return m.group(1).lower() if m else None


def analyse(game_ids: list[int], team_names: list[str]):
    valuables_hits = []
    generic_hits = []
    for game_id in game_ids:
        items = case_line_items(game_id)
        if items is None:
            continue
        b = brackets(game_id, team_names)

        # -- valuables-specific grouping (the named class): all valuables items in one Case
        # form ONE group, matching S4.2.2's "aggregate per insured event across all items".
        val_members = [li for li in items if class_of(li.name, VALUABLES_RE)]
        if len(val_members) >= 2:
            lo_hi = [(li, b.get(li.index, (0.0, float("inf")))) for li in val_members]
            positives = [li for li, (lo, hi) in lo_hi if lo > 0]
            zeros = [li for li, (lo, hi) in lo_hi if lo == 0]
            if len(positives) == 1 and len(zeros) == len(val_members) - 1:
                valuables_hits.append((game_id, lo_hi))

        # -- generic grouping: bucket by matched keyword-class, since "phone" and "watch"
        # are different classes even if both are "a discrete physical object".
        buckets: dict[str, list] = {}
        for li in items:
            c = class_of(li.name, GENERIC_OBJECT_RE)
            if c:
                buckets.setdefault(c, []).append(li)
        for cls, members in buckets.items():
            if len(members) < 2:
                continue
            lo_hi = [(li, b.get(li.index, (0.0, float("inf")))) for li in members]
            positives = [li for li, (lo, hi) in lo_hi if lo > 0]
            zeros = [li for li, (lo, hi) in lo_hi if lo == 0]
            if len(positives) == 1 and len(zeros) == len(members) - 1:
                generic_hits.append((game_id, cls, lo_hi))
    return valuables_hits, generic_hits


def fmt_bracket(lo: float, hi: float) -> str:
    return f"[{lo:.0f}, {'inf' if hi == float('inf') else f'{hi:.0f}'})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="1-44")
    args = parser.parse_args()
    start, _, end = args.games.partition("-")
    game_ids = list(range(int(start), int(end or start) + 1))
    team_names = teams()

    val_hits, gen_hits = analyse(game_ids, team_names)

    print(f"=== VALUABLES class (watch/ring/necklace/bracelet/earring/jewellery/...) ===")
    print(f"Cases scanned: {len(game_ids)}. Cases with >=2 valuables Line Items showing the")
    print(f"'one absorbs the pot, siblings settle at 0' pattern: {len(val_hits)}\n")
    for game_id, lo_hi in val_hits:
        print(f"  Game {game_id}:")
        for li, (lo, hi) in lo_hi:
            tag = "POSITIVE" if lo > 0 else "zero"
            print(f"    item {li.index:2d} [{tag:8s}] t={fmt_bracket(lo, hi):>16s}  {li.name}")
        print()

    print(f"=== GENERIC discrete-object classes (broader net, includes valuables) ===")
    print(f"Groups with the same pattern (n={len(gen_hits)}):\n")
    for game_id, cls, lo_hi in gen_hits:
        print(f"  Game {game_id}  class='{cls}':")
        for li, (lo, hi) in lo_hi:
            tag = "POSITIVE" if lo > 0 else "zero"
            print(f"    item {li.index:2d} [{tag:8s}] t={fmt_bracket(lo, hi):>16s}  {li.name}")
        print()

    # denominator context: how many Cases even HAVE >=2 valuables items to begin with,
    # regardless of whether the pattern fired -- this bounds how big the lead could ever be.
    n_multi_valuables = 0
    n_multi_generic_groups = 0
    for game_id in game_ids:
        items = case_line_items(game_id)
        if items is None:
            continue
        val_members = [li for li in items if class_of(li.name, VALUABLES_RE)]
        if len(val_members) >= 2:
            n_multi_valuables += 1
        buckets: dict[str, list] = {}
        for li in items:
            c = class_of(li.name, GENERIC_OBJECT_RE)
            if c:
                buckets.setdefault(c, []).append(li)
        n_multi_generic_groups += sum(1 for members in buckets.values() if len(members) >= 2)

    print(f"=== denominators ===")
    print(f"  Cases with >=2 valuables-class Line Items at all: {n_multi_valuables} / {len(game_ids)}")
    print(f"  Case x generic-class groups with >=2 members at all: {n_multi_generic_groups}")


if __name__ == "__main__":
    main()
