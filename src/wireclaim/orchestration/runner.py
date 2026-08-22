from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Callable

from api.client import EHLClient
from api.models import ForbiddenError, Game
from wireclaim.cases.archive import ArchiveExtractor, ExtractedCase
from wireclaim.domain.models import CaseReady
from wireclaim.pipeline.protocol import CaseProcessor
from wireclaim.state.database import StateStore

LOGGER = logging.getLogger(__name__)


class GameRunner:
    def __init__(
        self,
        *,
        client: EHLClient,
        extractor: ArchiveExtractor,
        processor: CaseProcessor,
        state: StateStore,
        key_retry_seconds: float,
        game_duration_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._extractor = extractor
        self._processor = processor
        self._state = state
        self._key_retry_seconds = key_retry_seconds
        self._game_duration_seconds = game_duration_seconds
        self._monotonic = monotonic
        self._sleep = sleep

    def run(self, game: Game) -> CaseReady:
        LOGGER.info("starting ingestion for game %s", game.id)
        self._state.transition(game, "key_pending")
        try:
            key = self._get_key_with_retry(game.id)
            self._state.transition(game, "key_available")
            extracted = self._extractor.extract(game.id, key)
            self._state.transition(game, "extracted")
            ready = self.to_case_ready(game, extracted)
            self._processor(ready)
            self._state.transition(game, "completed")
            LOGGER.info("downstream processing returned for game %s", game.id)
            return ready
        except Exception as exc:
            self._state.transition(game, "failed", error=str(exc)[:2000])
            raise

    def process_existing(self, game: Game) -> CaseReady:
        extracted = self._extractor.load_existing(game.id)
        ready = self.to_case_ready(game, extracted)
        self._processor(ready)
        self._state.transition(game, "completed")
        return ready

    def to_case_ready(self, game: Game, extracted: ExtractedCase) -> CaseReady:
        return CaseReady(
            game_id=game.id,
            start_time=game.start_time,
            deadline=game.start_time + timedelta(seconds=self._game_duration_seconds),
            case_dir=extracted.case_dir,
            input_dir=extracted.input_dir,
            policy_path=extracted.policy_path,
            description_path=extracted.description_path,
            invoices_path=extracted.invoices_path,
            image_paths=extracted.image_paths,
            manifest_path=extracted.manifest_path,
        )

    def _get_key_with_retry(self, game_id: int) -> str:
        deadline = self._monotonic() + self._key_retry_seconds
        delay = 0.25
        while True:
            try:
                return self._client.get_decryption_key(game_id)
            except ForbiddenError:
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    raise
                LOGGER.debug(
                    "key for game %s is not available yet; retrying shortly", game_id
                )
                self._sleep(min(delay, remaining))
                delay = min(delay * 2, 1.0)
