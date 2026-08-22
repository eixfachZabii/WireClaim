"""
Azure OpenAI / OpenAI LLM Client Module for WireClaim.

Provides functional helpers to query Azure OpenAI / OpenAI models for:
- Damage case analysis (policy coverage & violation detection)
- Fair value threshold (t) estimation
- Invoice extraction & OCR parsing

Environment Variables:
    AZURE_OPENAI_API_KEY: Azure OpenAI / OpenAI API Key.
    AZURE_OPENAI_ENDPOINT: Endpoint / Base URL (e.g. https://<your-resource>.openai.azure.com/v1 or custom gateway).
    AZURE_OPENAI_MODEL: Deployment / Model name (e.g. gpt-4o, o3-mini).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

# Robust dotenv loading
ENV_PATH = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)


def get_llm_client(
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> OpenAI:
    """Initialize and return an OpenAI / Azure OpenAI client.

    Args:
        api_key: API Key (defaults to `AZURE_OPENAI_API_KEY` or `OPENAI_API_KEY`).
        endpoint: Endpoint / Base URL (defaults to `AZURE_OPENAI_ENDPOINT`).

    Returns:
        Configured OpenAI client instance.

    Raises:
        ValueError: If no API key is provided or found in the environment.
    """
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
    )


def query_llm(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """Send a prompt to the LLM and return the generated text response.

    Uses `client.responses.create(...)` with fallback to `client.chat.completions.create(...)`.

    Args:
        prompt: The input text / instructions for the model.
        model: Model / deployment name (defaults to `AZURE_OPENAI_MODEL`).
        api_key: Optional explicit API key.
        endpoint: Optional explicit endpoint URL.

    Returns:
        str: Model text response.

    Example:
        >>> answer = query_llm("Is a broken windshield covered under comprehensive insurance?")
        >>> print(answer)
    """
    client = get_llm_client(api_key=api_key, endpoint=endpoint)
    target_model = model or os.getenv("AZURE_OPENAI_MODEL") or "gpt-4o"

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
        # Fallback to standard chat completions if responses.create is not supported by endpoint
        pass

    # Standard Chat Completions API fallback
    chat_response = client.chat.completions.create(
        model=target_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return str(chat_response.choices[0].message.content or "").strip()