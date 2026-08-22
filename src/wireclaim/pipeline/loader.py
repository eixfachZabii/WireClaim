from __future__ import annotations

import importlib

from wireclaim.pipeline.protocol import CaseProcessor


def load_processor(specification: str) -> CaseProcessor:
    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("processor must use the form 'module:function'")
    module = importlib.import_module(module_name)
    processor = getattr(module, attribute_name)
    if not callable(processor):
        raise TypeError(f"configured processor is not callable: {specification}")
    return processor
