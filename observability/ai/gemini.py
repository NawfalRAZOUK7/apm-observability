from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass


class GeminiEmbedError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _normalize_model(model: str) -> str:
    model = model.strip()
    if model.startswith("models/"):
        return model
    return f"models/{model}"


def _truncate_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise GeminiEmbedError(f"Gemini API error ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise GeminiEmbedError(f"Gemini API request failed: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise GeminiEmbedError("Gemini API response was not valid JSON.") from exc


@dataclass(frozen=True)
class GeminiEmbedClient:
    api_key: str
    model: str = "text-embedding-004"
    base_url: str = "https://generativelanguage.googleapis.com"
    timeout: float = 10.0
    max_chars: int = 8000
    min_delay_s: float = 0.0

    def _embed_url(self) -> str:
        model_name = _normalize_model(self.model)
        return f"{self.base_url}/v1beta/{model_name}:embedContent?key={self.api_key}"

    def embed_text(self, text: str) -> list[float]:
        payload = {
            "content": {"parts": [{"text": _truncate_text(text, self.max_chars)}]},
        }
        data = _post_json(self._embed_url(), payload, self.timeout)
        embedding = data.get("embedding") or {}
        values = embedding.get("values")
        if not isinstance(values, list):
            raise GeminiEmbedError("Gemini API response missing embedding values.")
        return values

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            if not text or not text.strip():
                raise GeminiEmbedError("Cannot embed empty text.")
            results.append(self.embed_text(text))
            if self.min_delay_s:
                time.sleep(self.min_delay_s)
        return results


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiEmbedError("GEMINI_API_KEY is not set.")

    model = (
        os.environ.get("GEMINI_EMBED_MODEL", "text-embedding-004").strip() or "text-embedding-004"
    )
    timeout = _env_float("GEMINI_EMBED_TIMEOUT", 10.0)
    max_chars = _env_int("GEMINI_EMBED_MAX_CHARS", 8000)
    min_delay_s = _env_float("GEMINI_EMBED_MIN_DELAY_S", 0.0)
    base_url = (
        os.environ.get("GEMINI_API_BASE_URL", "").strip()
        or "https://generativelanguage.googleapis.com"
    )

    client = GeminiEmbedClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_chars=max_chars,
        min_delay_s=min_delay_s,
    )
    return client.embed_texts(texts)
