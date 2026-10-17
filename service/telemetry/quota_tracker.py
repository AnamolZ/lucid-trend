"""Multi-key quota tracking, rate limit monitoring, and session telemetry."""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Constants for Google AI Studio Free Tier
FREE_TIER_RPM_LIMIT = 15
FREE_TIER_DAILY_LIMIT_PER_KEY = 1500

class QuotaTelemetryTracker:
    """Tracks session consumption, hourly rate limits, and multi-key quota capacity."""

    def __init__(self):
        self.session_calls = 0
        self.session_start = time.time()
        self.hourly_call_timestamps = []
        self._key_usage_today: Dict[str, int] = {}
        self._current_date_str = datetime.now().strftime("%Y-%m-%d")

    def _clean_hourly_timestamps(self):
        """Purges timestamps older than 60 seconds to track current RPM window."""
        now = time.time()
        self.hourly_call_timestamps = [t for t in self.hourly_call_timestamps if now - t < 60]

    def _ensure_date_rollover(self):
        """Resets daily counters on a new calendar day."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date_str:
            self._current_date_str = today
            self._key_usage_today = {}

    def record_call(self, key: str, model_name: str = ""):
        """Records an API call against telemetry and quota accounting."""
        self._ensure_date_rollover()
        self._clean_hourly_timestamps()

        self.session_calls += 1
        self.hourly_call_timestamps.append(time.time())

        masked_key = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        self._key_usage_today[masked_key] = self._key_usage_today.get(masked_key, 0) + 1

    def get_telemetry_banner(self, raw_keys: list, active_key_index: int, active_model: str) -> str:
        """Constructs an enterprise-grade telemetry banner."""
        self._ensure_date_rollover()
        self._clean_hourly_timestamps()

        total_keys = max(len(raw_keys), 1)
        total_pool_capacity = total_keys * FREE_TIER_DAILY_LIMIT_PER_KEY

        # Calculate consumed across known keys
        total_consumed = sum(self._key_usage_today.values())
        total_remaining = max(total_pool_capacity - total_consumed, 0)
        burn_rpm = len(self.hourly_call_timestamps)

        active_key = raw_keys[active_key_index] if active_key_index < len(raw_keys) else ""
        masked_active = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"

        headroom_pct = max(0.0, (1.0 - (burn_rpm / FREE_TIER_RPM_LIMIT)) * 100)
        consumed_pct = (total_consumed / total_pool_capacity) * 100 if total_pool_capacity > 0 else 0.0

        lines = [
            "=" * 78,
            "[TELEMETRY] Multi-Key Quota & Burn-Rate Status",
            "-" * 78,
            f"Active Model:           {active_model}",
            f"Active API Key:         Key #{active_key_index + 1} ({masked_active})",
            f"Session Calls:          {self.session_calls} call(s) made this runtime session",
            f"Current Burn Rate:      {burn_rpm} / {FREE_TIER_RPM_LIMIT} RPM ({headroom_pct:.1f}% RPM headroom)",
            f"Daily Pool Consumed:    {total_consumed} / {total_pool_capacity:,} requests ({consumed_pct:.2f}% consumed)",
            f"Total Pool Remaining:   {total_remaining:,} requests available across {total_keys} key(s)",
            "-" * 78,
            "Key Pool Health Breakdown:"
        ]

        for i, k in enumerate(raw_keys):
            m_key = k[:6] + "..." + k[-4:] if len(k) > 10 else f"Key #{i+1}"
            used = self._key_usage_today.get(m_key, 0)
            rem = max(FREE_TIER_DAILY_LIMIT_PER_KEY - used, 0)
            status_tag = "ACTIVE" if i == active_key_index else "READY"
            lines.append(f"  • Key #{i+1} ({m_key}): {used} used today | {rem:,} rem | [{status_tag}]")

        lines.append("=" * 78)
        return "\n".join(lines)

# Singleton global instance
telemetry_tracker = QuotaTelemetryTracker()
