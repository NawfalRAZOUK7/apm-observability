from __future__ import annotations

import random
from typing import Optional

from django.conf import settings

from .db_routing import is_safe_method, should_force_primary


class PrimaryReplicaRouter:
    """
    Route writes to primary (writer). Route reads to replicas or reader.
    """

    @staticmethod
    def _primary_alias() -> str:
        return "writer" if "writer" in settings.DATABASES else "default"

    @staticmethod
    def _reader_alias() -> str:
        if "reader" in settings.DATABASES:
            return "reader"
        return PrimaryReplicaRouter._primary_alias()

    def db_for_read(self, model, **hints) -> Optional[str]:
        if not is_safe_method() or should_force_primary():
            return self._primary_alias()

        replicas = getattr(settings, "REPLICA_DATABASES", [])
        if replicas:
            return random.choice(replicas)

        return self._reader_alias()

    def db_for_write(self, model, **hints) -> Optional[str]:
        return self._primary_alias()

    def allow_relation(self, obj1, obj2, **hints) -> Optional[bool]:
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> Optional[bool]:
        return db == "default"
