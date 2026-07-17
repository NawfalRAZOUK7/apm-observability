# alerting/management/commands/evaluate_alert_rules.py
"""Evaluate all enabled alert rules once, or continuously with --loop.

Scheduling options (pick one):
  - cron:      * * * * *  python manage.py evaluate_alert_rules
  - sidecar:   python manage.py evaluate_alert_rules --loop --interval 60
  - external:  a Kubernetes CronJob invoking the one-shot form
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from alerting.evaluator import evaluate_all


class Command(BaseCommand):
    help = "Evaluate enabled alert rules and route firings to the notification sink."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Run continuously.")
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Seconds between passes when --loop (default 60).",
        )

    def _run_once(self):
        results = evaluate_all()
        fired = [r for r in results if r["transitioned"]]
        self.stdout.write(f"evaluated {len(results)} rule(s); {len(fired)} state transition(s)")
        for r in fired:
            self.stdout.write(f"  -> {r['project']}/{r['rule']}: {r['state']} (value={r['value']})")
        return results

    def handle(self, *args, **opts):
        if not opts["loop"]:
            self._run_once()
            return
        interval = max(opts["interval"], 1)
        self.stdout.write(f"Evaluating alert rules every {interval}s (Ctrl-C to stop)...")
        while True:
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                self.stderr.write(f"evaluation error: {exc}")
            time.sleep(interval)
