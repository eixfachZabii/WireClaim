"""
Azure OpenAI / OpenAI LLM Client Module for WireClaim.

Provides functional helpers to query Azure OpenAI / OpenAI models for:
- Damage case analysis (policy coverage & violation detection)
- Fair value threshold (t) estimation
- Invoice extraction & OCR parsing

Environment Variables:
    AZURE_OPENAI_API_KEY: Azure OpenAI / OpenAI API Key.
    AZURE_OPENAI_ENDPOINT: Endpoint / Base URL (e.g. https://<your-resource>.openai.azure.com/v1 or custom gateway).
    AZURE_OPENAI_MODEL: Deployment / Model name (defaults to gpt-5.6-terra).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

DEFAULT_MODEL = "gpt-5.6-terra"

# Optional dotenv loading with stdlib fallback
try:
    from dotenv import find_dotenv, load_dotenv

    env_file = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent.parent.parent / ".env")
    load_dotenv(dotenv_path=env_file, override=True)
except ImportError:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def warm_llm_resources() -> None:
    import openai.resources.chat
    import openai.resources.responses


def get_llm_client(
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Any:
    """Initialize and return an OpenAI / Azure OpenAI client.

    Args:
        api_key: API Key (defaults to `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY`).
        endpoint: Endpoint / Base URL (defaults to `AZURE_OPENAI_ENDPOINT`).

    Returns:
        Configured OpenAI client instance.

    Raises:
        ValueError: If no API key is provided or found in the environment.
    """
    from openai import OpenAI

    resolved_key = (
        api_key
        or os.getenv("AZURE_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()

    if not resolved_key:
        raise ValueError(
            "Missing API Key. Please set 'AZURE_OPENAI_API_KEY' (or 'OPENAI_API_KEY') in your .env file."
        )

    resolved_endpoint = (
        endpoint
        or os.getenv("AZURE_OPENAI_ENDPOINT")
        or None
    )

    return OpenAI(
        api_key=resolved_key,
        base_url=resolved_endpoint,
        max_retries=0,
    )


def get_model_name(model: Optional[str] = None) -> str:
    return model or os.getenv("AZURE_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL


def query_llm(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """Send a prompt to the LLM and return the generated text response."""
    client = get_llm_client(api_key=api_key, endpoint=endpoint)
    target_model = get_model_name(model)

    # Try responses.create first (if using Azure / OpenAI Responses API)
    try:
        if hasattr(client, "responses") and callable(getattr(client.responses, "create", None)):
            response = client.responses.create(
                model=target_model,
                input=prompt,
            )
            if hasattr(response, "output_text") and response.output_text:
                return str(response.output_text).strip()
            if hasattr(response, "output") and response.output:
                return str(response.output).strip()
    except Exception:
        pass

    # Standard Chat Completions API fallback
    chat_response = client.chat.completions.create(
        model=target_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return str(chat_response.choices[0].message.content or "").strip()