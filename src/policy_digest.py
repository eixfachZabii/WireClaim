from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from src.api import get_llm_client, get_model_name

CACHE_DIR = Path("var/policy_digests")
DIGEST_TIMEOUT_SECONDS = 20.0
_memory_cache: dict[str, str] = {}
_lock = threading.Lock()

PROMPT = """Condense this insurance policy into at most 400 words of pricing evidence for invoice Line Items.

Include only:
- indemnity basis and depreciation rules
- affected-parts-only, repair scope, and ancillary-work rules
- like-for-like, upgrade, and betterment rules
- material exclusions, proof requirements, deductibles, sub-limits, and location restrictions

Use compact bullet points. Do not recommend Charge, Limit, or Fair Value values."""



def digest_policy_text(policy_text: str) -> str:
    digest_key = hashlib.sha256(policy_text.encode("utf-8")).hexdigest()
    with _lock:
        cached = _memory_cache.get(digest_key)
    if cached is not None:
        return cached

    cache_path = CACHE_DIR / f"{digest_key}.txt"
    if cache_path.exists():
        digest = cache_path.read_text(encoding="utf-8")
    else:
        response = get_llm_client().chat.completions.create(
            model=get_model_name(),
            timeout=DIGEST_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": policy_text},
            ],
        )
        digest = str(response.choices[0].message.content or "")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(digest, encoding="utf-8")
    with _lock:
        _memory_cache[digest_key] = digest
    return digest
