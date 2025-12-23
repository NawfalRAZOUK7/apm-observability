from __future__ import annotations

import random
from typing import Optional

from django.conf import settings


class PrimaryReplicaRouter:
    """
    Route reads to replicas when configured, writes to primary.
    """

    def db_for_read(self, model, **hints) -> Optional[str]:
        replicas = getattr(settings, "REPLICA_DATABASES", [])
        if replicas:
            return random.choice(replicas)
        return "default"

    def db_for_write(self, model, **hints) -> Optional[str]:
        return "default"

    def allow_relation(self, obj1, obj2, **hints) -> Optional[bool]:
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> Optional[bool]:
        return db == "default"
