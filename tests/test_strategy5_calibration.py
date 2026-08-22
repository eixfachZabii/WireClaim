import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.calibrate_strategy5 import (
    FactorCandidate,
    ProposalRun,
    apply_recommendation,
    current_regime_games,
    evaluate_runs,
    recommend_candidate,
    scale_submission,
)
from src.services.strategies.strategy5.config import Strategy5Config, load_config


class Strategy5CalibrationTests(unittest.TestCase):
    def test_calibration_never_carries_field_evidence_across_regimes(self) -> None:
        completed = (1, 43, 44, 60, 81, 82, 90)

        self.assertEqual(current_regime_games(completed, 81), (44, 60, 81))
        self.assertEqual(current_regime_games(completed, 90), (82, 90))

    def test_scaling_keeps_axes_separate_and_preserves_zero_limits(self) -> None:
        submission = {1: (100.0, 50.0), 2: (80.0, 0.0)}

        alpha = scale_submission(submission, charge_ratio=0.9)
        beta = scale_submission(submission, limit_ratio=1.1)

        self.assertEqual(alpha, {1: (90.0, 50.0), 2: (72.0, 0.0)})
        self.assertEqual(beta, {1: (100.0, 55.0), 2: (80.0, 0.0)})

    def test_recommendation_requires_enough_games_noise_clearance_and_both_folds(self) -> None:
        config = Strategy5Config(minimum_calibration_games=2, noise_floor_18_games=10.0)
        strong = FactorCandidate("alpha_down", "alpha", 0.9, ((1, 8.0), (2, 7.0)))
        one_fold = FactorCandidate("beta_down", "beta", 0.9, ((1, 20.0), (2, -1.0)))

        self.assertIsNone(recommend_candidate((strong,), Strategy5Config(), game_count=2))
        self.assertEqual(recommend_candidate((strong, one_fold), config, game_count=2), strong)

    def test_replay_evaluates_both_factor_directions_against_the_same_field(self) -> None:
        runs = (
            ProposalRun(1, {1: (100.0, 50.0)}),
            ProposalRun(2, {1: (100.0, 50.0)}),
        )
        config = Strategy5Config(
            minimum_calibration_games=2,
            noise_floor_18_games=0.0,
            factor_step=0.1,
        )

        def snapshot(game_id):
            return SimpleNamespace(game_id=game_id, line_items=(1,))

        def replay(snap, submission):
            charge, limit = submission[1]
            return SimpleNamespace(net=-abs(charge - 90.0) - abs(limit - 50.0))

        report = evaluate_runs(runs, config, snapshot_fn=snapshot, replay_fn=replay)

        self.assertEqual(report.recommendation.name, "alpha_down")
        self.assertEqual(report.game_ids, (1, 2))
        self.assertEqual(report.recommendation.total_delta, 20.0)

    def test_the_derived_zero_limit_threshold_cannot_be_tuned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "models": ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.4-mini"],
                        "zero_limit_violation_threshold": 0.5,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_config(path)

    def test_apply_changes_at_most_the_recommended_factor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "models": ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.4-mini"],
                        "coverage_model": "gpt-5.6-terra",
                        "ALPHA_FAC": 1.0,
                        "BETA_FAC": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            recommendation = FactorCandidate(
                "alpha_down",
                "alpha",
                0.9,
                ((1, 30_000.0), (2, 30_000.0)),
            )

            apply_recommendation(recommendation, path)
            updated = load_config(path)

        self.assertEqual(updated.alpha_factor, 0.9)
        self.assertEqual(updated.beta_factor, 1.0)


if __name__ == "__main__":
    unittest.main()
