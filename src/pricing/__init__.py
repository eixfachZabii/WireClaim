"""The deterministic engine: turns `Evidence` into a Charge and a Limit, and nothing else
does (ADR 0001). Price Memory moved to `src.evidence.memory` -- it is a channel that
*produces* evidence, not part of the engine that prices it."""
