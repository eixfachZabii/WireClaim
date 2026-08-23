"""Google ADK runtime: the one place a Gemini call happens.

Why this exists at all
----------------------
The tournament ran on Azure OpenAI (`src/api/llm.py`, `gpt-5.6-terra`). That deployment was
decommissioned after the event and now returns `404 - Could not find an existing deployment`,
which left the evidence layer with no reachable model and the open question in H28 -- *can a
model asked to choose among priced anchors beat unaided retrieval?* -- untestable.

This is the replacement, deliberately modelled on the runtime already proven in the sibling
WealthWatcher project rather than invented here: an ADK `LlmAgent` carrying a Pydantic
`output_schema`, driven through `InMemoryRunner`'s async event stream, with the answer selected
on `event.is_final_response()` so intermediate thought parts are never mistaken for the result.

Three things it borrows because WealthWatcher paid for them
-----------------------------------------------------------
* **Credentials are bridged into `os.environ`.** `google-genai` authenticates from the process
  environment, not from whatever object loaded the `.env`, and the failure mode is a confusing
  "No API key was provided" when the key is plainly on disk.
* **One long-lived event loop on a daemon thread**, not `asyncio.run()` per call. A fresh loop
  per call leaves the genai async client's finalizer running against a closed loop, which
  raises `RuntimeError: Event loop is closed` at teardown.
* **Structured parsing tolerates fences and prose.** An `output_schema` agent usually returns
  bare JSON, but not always; the outermost `{...}` is extracted before validation.

What is deliberately *not* borrowed: WealthWatcher's retry/backoff ladder, its mock provider and
its tool-calling agents. This module makes single-turn structured calls for offline experiments,
never inside a 60-second Game window, so a failed call can simply be skipped and counted.

**Not on the tournament path.** `main.run_game` still routes through `src/api/llm.py`. Nothing
here is wired into submission; it exists so the evidence-layer questions can be answered.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import os
import re
import threading
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_APP_NAME = "wireclaim"
_USER_ID = "estimator"

#: Default model. Overridable with `GEMINI_MODEL`; the flash line is markedly cheaper and is
#: what the estimator experiments use for their fan-out.
DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_FLASH = "gemini-3.7-flash"


class ModelUnavailable(RuntimeError):
    """No credentials, or the SDK is not installed. Raised rather than silently degrading."""


def _load_env() -> None:
    """Bridge `.env` into the process environment, which is where google-genai reads.

    Deliberately does not depend on pydantic-settings: this repository loads `.env` with
    `set -a && . ./.env`, and a module that only works under one of those two is a trap.
    """
    if os.environ.get("GOOGLE_API_KEY"):
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
        return
    path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name.startswith(("GOOGLE_", "GEMINI_")) and value:
            os.environ.setdefault(name, value)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


def model_name(flash: bool = False) -> str:
    _load_env()
    if flash:
        return os.environ.get("GEMINI_MODEL_FLASH") or DEFAULT_FLASH
    return os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL


def available() -> bool:
    """True when a call could plausibly succeed. Cheap; does not hit the network."""
    _load_env()
    if not os.environ.get("GOOGLE_API_KEY"):
        return False
    try:
        import google.adk  # noqa: F401
    except ImportError:
        return False
    return True


# ------------------------------------------------------------------ the shared loop

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _swallow_loop_closed(loop, context) -> None:
    exc = context.get("exception")
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        return
    loop.default_exception_handler(context)


def _get_loop() -> asyncio.AbstractEventLoop:
    """The process-wide runtime loop, started on first use and kept alive."""
    global _loop
    with _loop_lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        ready = threading.Event()

        def run() -> None:
            global _loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.set_exception_handler(_swallow_loop_closed)
            _loop = loop
            ready.set()
            loop.run_forever()

        threading.Thread(target=run, name="adk-runtime", daemon=True).start()
        ready.wait(timeout=10)
        if _loop is None:
            raise ModelUnavailable("could not start the ADK runtime loop")
        atexit.register(lambda: _loop and not _loop.is_closed() and _loop.call_soon_threadsafe(_loop.stop))
        return _loop


# ------------------------------------------------------------------------ the call


def build_agent(name: str, instruction: str, schema: type[T], *, flash: bool = False):
    """An `LlmAgent` that must answer as `schema`.

    An `output_schema` agent cannot use tools or transfer control -- that is an ADK constraint,
    not a choice, and it suits this use exactly: the model reads and judges, the engine prices
    (ADR 0001).
    """
    if not available():
        raise ModelUnavailable("GOOGLE_API_KEY is not set, or google-adk is not installed")
    from google.adk.agents import LlmAgent

    return LlmAgent(
        name=name,
        model=model_name(flash=flash),
        instruction=instruction,
        output_schema=schema,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


async def _run_async(agent, prompt: str) -> str:
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=agent, app_name=_APP_NAME)
    session = await runner.session_service.create_session(app_name=_APP_NAME, user_id=_USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    final = ""
    async for event in runner.run_async(
        user_id=_USER_ID, session_id=session.id, new_message=message
    ):
        # Select on the FINAL event, not "last text seen" -- intermediate thought parts are
        # not the answer.
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text for p in event.content.parts if p.text)
            if text:
                final = text
    return final


def run_structured(agent, prompt: str, schema: type[T], timeout: float = 120.0) -> T:
    """One agent turn, parsed as `schema`. Raises on timeout or unparseable output."""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(_run_async(agent, prompt), loop)
    raw = future.result(timeout=timeout)
    text = (raw or "").strip()
    if not text:
        raise ValueError("the model returned no text")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return schema.model_validate(json.loads(match.group(0) if match else text))


__all__ = [
    "DEFAULT_FLASH",
    "DEFAULT_MODEL",
    "ModelUnavailable",
    "available",
    "build_agent",
    "model_name",
    "run_structured",
]
