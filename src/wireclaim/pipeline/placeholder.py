from __future__ import annotations

import logging

from wireclaim.domain.models import CaseReady

LOGGER = logging.getLogger(__name__)


def process_case(case: CaseReady) -> None:
    """Default downstream hook, intentionally limited to announcing readiness."""
    LOGGER.info(
        "game %s is ready for analysis at %s (%s image(s), deadline %s)",
        case.game_id,
        case.input_dir,
        len(case.image_paths),
        case.deadline.isoformat(),
    )
    # TODO(analysis): Parse invoices.pdf into indexed line items.
    # TODO(analysis): Evaluate policy coverage and damage relationship per item.
    # TODO(pricing): Estimate fair gross totals and produce a/b recommendations.
    # TODO(api-submission): Hand validated recommendations to the future src/api
    # submission interface. The initial setup must not post them automatically.

