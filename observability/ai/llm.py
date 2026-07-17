# observability/ai/llm.py
"""Pluggable LLM text-generation provider (Phase 13).

Mirrors the embedder (Phase 8): selected by env, free/offline by default. When no
LLM is configured, callers fall back to deterministic templates/heuristics, so
every LLM feature degrades gracefully to a $0 path.

    LLM_PROVIDER = none | gemini | ollama          (default: none)
    GEMINI_API_KEY, GEMINI_TEXT_MODEL              (default gemini-1.5-flash)
    OLLAMA_URL, OLLAMA_TEXT_MODEL                  (default llama3.2)

Stdlib-only (urllib), so it adds no dependency.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    """Raised when no LLM is configured; callers should fall back."""


def active_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "none").strip().lower() or "none"


def is_available() -> bool:
    provider = active_provider()
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())
    if provider == "ollama":
        return bool(os.environ.get("OLLAMA_URL", "").strip())
    return False


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise LLMError(f"LLM HTTP error ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError("LLM response was not valid JSON.") from exc


def _gemini(prompt: str, system: str | None, timeout: float) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-1.5-flash").strip()
    base = (
        os.environ.get("GEMINI_API_BASE_URL", "").strip()
        or "https://generativelanguage.googleapis.com"
    )
    url = f"{base}/v1beta/models/{model}:generateContent?key={key}"
    text = (system + "\n\n" if system else "") + prompt
    data = _post_json(url, {"contents": [{"parts": [{"text": text}]}]}, timeout)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Gemini response missing text.") from exc


def _ollama(prompt: str, system: str | None, timeout: float) -> str:
    base = (os.environ.get("OLLAMA_URL", "").strip() or "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_TEXT_MODEL", "llama3.2").strip()
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    data = _post_json(f"{base}/api/generate", payload, timeout)
    response = data.get("response")
    if not isinstance(response, str):
        raise LLMError("Ollama response missing text.")
    return response


def complete(prompt: str, *, system: str | None = None, timeout: float = 30.0) -> str:
    """Generate text with the configured provider, or raise LLMUnavailable."""
    provider = active_provider()
    if provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            raise LLMUnavailable("GEMINI_API_KEY not set.")
        return _gemini(prompt, system, timeout)
    if provider == "ollama":
        return _ollama(prompt, system, timeout)
    raise LLMUnavailable("No LLM provider configured (set LLM_PROVIDER).")
