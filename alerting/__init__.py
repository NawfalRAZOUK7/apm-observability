"""Tenant-defined alert rules + scheduled evaluation (Phase 10).

Turns the on-demand anomaly detector (Phase 8) and static Prometheus alerts into
first-class, per-tenant alert rules that a scheduler evaluates continuously and
routes through the notification sink (Phase 4) into incidents (Phase 9).
"""
