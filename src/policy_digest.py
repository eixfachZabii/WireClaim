"""
Policy digest: one LLM call per distinct policy wording.

Policies are 800-1300 line insurance wordings and repeat across Cases. This
module condenses a policy into a short digest of the rules that matter for
pricing line items (indemnity basis, affected-parts-only rule, like-for-like
materials, exclusions, deductibles), keyed by the SHA-256 of the policy text.

Digests are cached in memory and on disk (`var/policy_digests/<sha>.txt`), so
a repeated policy costs nothing at game time.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from openai import OpenAI

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_AZURE_ENDPOINT = "https://claim-to-fame-ai.openai.azure.com/openai/v1/"

CACHE_DIR = Path(__file__).resolve().parent.parent / "var" / "policy_digests"

DIGEST_PROMPT = """\
You are a senior insurance claims expert. Condense the following insurance
policy wording into a compact digest (max ~400 words) of everything that
matters when deciding how much may fairly be paid for an invoice line item:

1. Indemnity basis: what is reimbursed for damaged property (repair cost?),
   for destroyed/lost property (new replacement price? market value?), and any
   depreciation or age rules.
2. Scope-of-repair rules: affected-parts-only, precautionary/preventive work,
   continuous surfaces, ancillary work included in a repair (drying, disposal,
   substrate preparation, final cleaning, testing of installations, etc.).
3. Material/quality rules: like-for-like standard, treatment of upgrades or
   betterment versus the pre-loss standard.
4. Relevant exclusions and proof requirements (e.g. technical report needed).
5. Deductibles, sums insured, sub-limits, insured location restrictions.

Write it as terse bullet points a claims adjuster can apply per line item.
"""

_memory_cache: dict[str, str] = {}
_lock = threading.Lock()


def _get_client(api_key: str | None = None) -> OpenAI:
    key = (
        api_key
        or os.environ.get("AZURE_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_KEY")
    )
    if not key:
        raise ValueError(
            "Missing API key. Set 'AZURE_OPENAI_API_KEY' (or 'OPENAI_API_KEY' / "
            "'OPENAI_KEY') in the environment or .env file."
        )
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or DEFAULT_AZURE_ENDPOINT
    if not endpoint.startswith(("http://", "https://")):
        endpoint = DEFAULT_AZURE_ENDPOINT
    return OpenAI(api_key=key, base_url=endpoint, timeout=45.0, max_retries=1)


def digest_policy(
    policy_path: Path,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """Return a compact pricing-relevant digest of the policy file, cached by hash."""
    policy_text = policy_path.read_text(encoding="utf-8", errors="replace")
    return digest_policy_text(policy_text, model=model, api_key=api_key)


def digest_policy_text(
    policy_text: str,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """Return a compact pricing-relevant digest of the policy text, cached by hash."""
    digest_key = hashlib.sha256(policy_text.encode("utf-8")).hexdigest()

    with _lock:
        cached = _memory_cache.get(digest_key)
    if cached is not None:
        return cached

    cache_file = CACHE_DIR / f"{digest_key}.txt"
    if cache_file.exists():
        digest = cache_file.read_text(encoding="utf-8")
        with _lock:
            _memory_cache[digest_key] = digest
        return digest

    client = _get_client(api_key)
    model_name = (
        model
        or os.environ.get("AZURE_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or DEFAULT_MODEL
    )
    response = client.chat.completions.create(
        model=model_name,
        temperature=0.0,
        messages=[
            {"role": "system", "content": DIGEST_PROMPT},
            {"role": "user", "content": policy_text},
        ],
    )
    digest = response.choices[0].message.content or ""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(digest, encoding="utf-8")
    with _lock:
        _memory_cache[digest_key] = digest
    return digest


def main() -> None:
    """Pre-warm the digest cache from every decrypted case under var/cases."""
    cases_dir = Path(__file__).resolve().parent.parent / "var" / "cases"
    for policy_path in sorted(cases_dir.glob("*/policy.txt")):
        digest_policy(policy_path)
        print(f"digested {policy_path.parent.name}")


if __name__ == "__main__":
    main()
