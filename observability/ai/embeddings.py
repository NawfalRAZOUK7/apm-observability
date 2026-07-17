# observability/ai/embeddings.py
"""Provider-pattern embedder dispatch (Phase 8).

Selects the embedding backend by env var, defaulting to the free/local one so
the platform runs offline at $0. Flip to Gemini for production quality with no
schema change (both emit 768-dim vectors).

    EMBED_PROVIDER=local   -> Ollama nomic-embed-text  (default, free/offline)
    EMBED_PROVIDER=gemini  -> Gemini text-embedding-004
"""
from __future__ import annotations

import os
from collections.abc import Iterable


class EmbedError(RuntimeError):
    pass


def active_provider() -> str:
    return os.environ.get("EMBED_PROVIDER", "local").strip().lower() or "local"


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Embed texts using the configured provider. Raises EmbedError on failure."""
    provider = active_provider()
    if provider == "gemini":
        from .gemini import GeminiEmbedError, embed_texts as gemini_embed

        try:
            return gemini_embed(texts)
        except GeminiEmbedError as exc:
            raise EmbedError(str(exc)) from exc

    # Default: local Ollama.
    from .local import LocalEmbedError, embed_texts as local_embed

    try:
        return local_embed(texts)
    except LocalEmbedError as exc:
        raise EmbedError(str(exc)) from exc
