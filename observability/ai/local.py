# observability/ai/local.py
"""Local embedder: Ollama `nomic-embed-text` (Phase 8).

Free, offline replacement for Gemini embeddings. `nomic-embed-text` produces
768-dim vectors — a drop-in for the existing `VectorField(dimensions=768)`, so
no schema change is needed when switching providers.

    EMBED_PROVIDER=local
    OLLAMA_URL=http://ollama:11434
    OLLAMA_EMBED_MODEL=nomic-embed-text
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterable


class LocalEmbedError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LocalEmbedError(f"Ollama error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise LocalEmbedError(f"Ollama request failed: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LocalEmbedError("Ollama response was not valid JSON.") from exc


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    base_url = (os.environ.get("OLLAMA_URL", "").strip() or "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip() or "nomic-embed-text"
    timeout = float(os.environ.get("OLLAMA_EMBED_TIMEOUT", "30") or 30)
    url = f"{base_url}/api/embeddings"

    results: list[list[float]] = []
    for text in texts:
        if not text or not text.strip():
            raise LocalEmbedError("Cannot embed empty text.")
        data = _post_json(url, {"model": model, "prompt": text}, timeout)
        values = data.get("embedding")
        if not isinstance(values, list) or not values:
            raise LocalEmbedError("Ollama response missing embedding values.")
        results.append(values)
    return results
