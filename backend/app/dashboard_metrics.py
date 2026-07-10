"""
Dashboard metrics collection: real-time system stats for the ops dashboard.
Tracks: requests, errors, latency, cache, inference, health.
"""
import time
from collections import deque
from threading import Lock
from datetime import datetime, timedelta

class MetricsCollector:
    """Thread-safe metrics collection for the dashboard."""

    def __init__(self):
        self.lock = Lock()
        # Request tracking (keep last 100)
        self.requests = deque(maxlen=100)
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.total_latency = 0.0

        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0

        # Inference metrics
        self.inference_count = 0
        self.total_inference_time = 0.0
        self.inference_errors = 0

        # Rate tracking (per minute)
        self.minute_requests = deque(maxlen=60)  # Last 60 minutes

    def record_request(self, endpoint, status_code, latency_ms, cached=False):
        """Record an API request."""
        with self.lock:
            self.request_count += 1
            self.total_latency += latency_ms

            if status_code >= 400:
                self.error_count += 1

            if cached:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

            self.requests.append({
                "timestamp": datetime.now().isoformat(),
                "endpoint": endpoint,
                "status": status_code,
                "latency_ms": latency_ms,
                "cached": cached,
            })

    def record_inference(self, latency_ms, error=False):
        """Record an LLM inference call."""
        with self.lock:
            self.inference_count += 1
            self.total_inference_time += latency_ms
            if error:
                self.inference_errors += 1

    def get_stats(self):
        """Get current metrics snapshot."""
        with self.lock:
            uptime_sec = time.time() - self.start_time
            uptime_hours = uptime_sec / 3600

            avg_latency = (self.total_latency / self.request_count) if self.request_count > 0 else 0
            avg_inference = (self.total_inference_time / self.inference_count) if self.inference_count > 0 else 0

            cache_hit_rate = (
                100 * self.cache_hits / (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses) > 0
                else 0
            )

            error_rate = (
                100 * self.error_count / self.request_count
                if self.request_count > 0
                else 0
            )

            # Calculate RPS (requests in last minute)
            now = time.time()
            recent_requests = [
                r for r in self.requests
                if (now - time.mktime(datetime.fromisoformat(r["timestamp"]).timetuple())) < 60
            ]
            rps = len(recent_requests) / 60  # Rough estimate

            inference_error_rate = (
                100 * self.inference_errors / self.inference_count
                if self.inference_count > 0
                else 0
            )

            return {
                "uptime_hours": round(uptime_hours, 1),
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "error_rate_pct": round(error_rate, 1),
                "avg_latency_ms": round(avg_latency, 1),
                "current_rps": round(rps, 2),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate_pct": round(cache_hit_rate, 1),
                "inference_calls": self.inference_count,
                "avg_inference_ms": round(avg_inference, 1),
                "inference_errors": self.inference_errors,
                "inference_error_rate_pct": round(inference_error_rate, 1),
                "recent_requests": list(self.requests)[-20:],  # Last 20 for the dashboard
            }

    def health_status(self):
        """Determine overall health."""
        stats = self.get_stats()

        # Green: all good
        if (stats["error_rate_pct"] < 5 and
            stats["cache_hit_rate_pct"] > 50 and
            stats["current_rps"] < 0.5):
            return "HEALTHY"

        # Yellow: minor issues
        elif (stats["error_rate_pct"] < 10 or
              stats["cache_hit_rate_pct"] > 30 or
              stats["inference_error_rate_pct"] < 10):
            return "DEGRADED"

        # Red: critical issues
        else:
            return "CRITICAL"

# Global instance
metrics = MetricsCollector()
