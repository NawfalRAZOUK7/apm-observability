"""Embedder provider-dispatch tests (Phase 8)."""

from __future__ import annotations

from django.test import SimpleTestCase

from observability.ai import embeddings, local


class EmbedderDispatchTests(SimpleTestCase):
    def test_defaults_to_local(self):
        with self.settings():
            import os

            os.environ.pop("EMBED_PROVIDER", None)
            self.assertEqual(embeddings.active_provider(), "local")

    def test_local_provider_used(self):
        captured = {}

        def fake_local(texts):
            captured["texts"] = list(texts)
            return [[0.1] * 768]

        original = local.embed_texts
        local.embed_texts = fake_local
        import os

        os.environ["EMBED_PROVIDER"] = "local"
        try:
            vecs = embeddings.embed_texts(["hello"])
        finally:
            local.embed_texts = original
            os.environ.pop("EMBED_PROVIDER", None)

        self.assertEqual(len(vecs[0]), 768)  # matches VectorField(dimensions=768)
        self.assertEqual(captured["texts"], ["hello"])

    def test_local_error_wrapped_as_embed_error(self):
        def boom(texts):
            raise local.LocalEmbedError("ollama down")

        original = local.embed_texts
        local.embed_texts = boom
        import os

        os.environ["EMBED_PROVIDER"] = "local"
        try:
            with self.assertRaises(embeddings.EmbedError):
                embeddings.embed_texts(["x"])
        finally:
            local.embed_texts = original
            os.environ.pop("EMBED_PROVIDER", None)

    def test_gemini_missing_key_raises_embed_error(self):
        import os

        os.environ["EMBED_PROVIDER"] = "gemini"
        os.environ.pop("GEMINI_API_KEY", None)
        try:
            with self.assertRaises(embeddings.EmbedError):
                embeddings.embed_texts(["x"])
        finally:
            os.environ.pop("EMBED_PROVIDER", None)
