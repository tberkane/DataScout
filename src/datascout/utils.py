"""Shared helpers: the LLM call, output cleanup and a portable timeout."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

from litellm import completion

from .configs import LLMConfig

T = TypeVar("T")
D = TypeVar("D")


def perform_completion(prompt: str, llm_config: LLMConfig) -> Any:
    """Send a single-message chat completion request through litellm.

    Args:
        prompt: The user message.
        llm_config: Model, API key and temperature to use.

    Returns:
        The litellm ``ModelResponse``.
    """
    return completion(
        model=llm_config.model,
        api_key=llm_config.api_key,
        temperature=llm_config.temperature,
        messages=[{"role": "user", "content": prompt}],
    )


def completion_text(prompt: str, llm_config: LLMConfig) -> str:
    """Return the text content of a completion for ``prompt``.

    Raises:
        ValueError: If the model returned no text content.
    """
    content = perform_completion(prompt, llm_config).choices[0].message.content
    if not content:
        raise ValueError(f"The LLM ({llm_config.model}) returned an empty response")
    return str(content)


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences (```` ```json ````, ```` ```python ````, ```` ``` ````) from LLM output."""
    lines = [line for line in text.strip().splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()


def normalize_variable_name(name: str) -> str:
    """Normalize a query-template variable name: lowercase, spaces replaced by underscores."""
    return name.lower().replace(" ", "_")


def timeout_function(
    func: Callable[..., T],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    timeout: float = 5,
    default_value: D = None,  # type: ignore[assignment]
) -> T | D:
    """Call ``func(*args, **kwargs)`` and give up after ``timeout`` seconds.

    The call runs in a daemon thread, so this works from any thread and on any OS. A call that times
    out keeps running in the background until it returns; its result is discarded.

    Args:
        func: Function to call.
        args: Positional arguments for ``func``.
        kwargs: Keyword arguments for ``func``.
        timeout: Time limit in seconds.
        default_value: Value returned if the call times out.

    Returns:
        The function's result, or ``default_value`` on timeout.

    Raises:
        Exception: Whatever ``func`` raises, if it finishes in time.
    """
    outcome: dict[str, Any] = {}

    def target() -> None:
        try:
            outcome["result"] = func(*args, **(kwargs or {}))
        except BaseException as exc:  # re-raised in the caller's thread
            outcome["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return default_value
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]  # type: ignore[no-any-return]
