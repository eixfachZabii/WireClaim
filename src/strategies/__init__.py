"""WireClaim Strategy Tracks: the router (`router.py`), the always-on blind floor
(`fast_path.py`), and the live estimator (`strategy2/`). `strategy1` and `strategy3` are
priced identically by `STRATEGY_PRIORITIES` below but live in `src.legacy` -- see that
package's docstring for why they still run at all.

`STRATEGY_PRIORITIES` lives here, and only here, because it is metadata about the tracks
themselves rather than about the router or the coordinator. It used to be declared in both
`strategy_router.py` and `submission_coordinator.py`, and the two copies had already drifted
apart: the router had Strategy 2 winning while the coordinator still ranked Strategy 3
above it, so our own submission logs labelled the winning track with the wrong priority.
"""

#: Higher wins. A source not listed here scores 0 and therefore loses to every known track,
#: which is the safe default for a typo in a `Proposal.source`. Keyed by `Proposal.source`,
#: a string tag -- not by module path, so `strategy1`/`strategy3` living in `src.legacy`
#: does not touch this dict.
#:
#: Strategy 2 is top because it is the only track whose constants are fitted to the
#: reconstructed Fair Values, and the only one that always answers. 1 and 3 keep running as
#: a free ensemble and a disagreement signal until Strategy 2 has a measured sigma of its
#: own; see `docs/brainstorm/sebi/strats/review/strategy2-plan.md`.
STRATEGY_PRIORITIES = {"strategy1": 1, "strategy3": 2, "strategy2": 3}

__all__ = ["STRATEGY_PRIORITIES"]
