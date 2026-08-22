"""WireClaim Strategy Tracks.

`STRATEGY_PRIORITIES` lives here, and only here, because it is metadata about the tracks
themselves rather than about the router or the coordinator. It used to be declared in both
`strategy_router.py` and `submission_coordinator.py`, and the two copies had already drifted
apart: the router had Strategy 2 winning while the coordinator still ranked Strategy 3
above it, so our own submission logs labelled the winning track with the wrong priority.
"""

#: Higher wins. A source not listed here scores 0 and therefore loses to every known track,
#: which is the safe default for a typo in a `Proposal.source`.
#:
#: Strategy 2 is the highest-priority individual track because its constants are fitted to
#: reconstructed Fair Values. Once both Strategy 2 and Strategy 5 finish, their explicit
#: max/zero merge supersedes either individual Proposal.
STRATEGY_PRIORITIES = {
    "strategy1": 1,
    "strategy3": 2,
    "strategy4": 2,
    "strategy5": 2,
    "strategy2": 3,
    "strategy2+5": 4,
}

__all__ = ["STRATEGY_PRIORITIES"]
