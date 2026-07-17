"""Notification delivery: the provider-pattern sink.

Receives Alertmanager webhooks, records every notification, and fans them out to
pluggable channel providers (sink/console/slack/discord/ntfy) selected by env.
The same delivery code path is used whether the target is the local mock sink or
a real provider -- see docs/ROADMAP.md, Phase 4 and Appendix A.
"""
