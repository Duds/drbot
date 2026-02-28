"""
Prometheus metrics for Remy observability.

Exposes histograms, counters, and gauges for request latency, API calls,
token usage, and system health.

Usage:
    from remy.analytics.metrics import (
        REQUEST_LATENCY, API_CALLS_TOTAL, CONTEXT_TOKENS,
        observe_request_timing, increment_api_call
    )

    # Record request timing
    observe_request_timing(timing)

    # Increment API call counter
    increment_api_call("anthropic", "claude-sonnet-4-6", "tool_use")
"""

from prometheus_client import Counter, Histogram, Gauge, Info

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .timing import RequestTiming

# Request latency by phase (in seconds)
REQUEST_LATENCY = Histogram(
    "remy_request_latency_seconds",
    "Request latency by processing phase",
    ["phase"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120],
)

# Time to first token (TTFT) - critical UX metric
TTFT_SECONDS = Histogram(
    "remy_ttft_seconds",
    "Time to first token from Claude API",
    buckets=[0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20],
)

# Total API calls by provider/model/call_site
API_CALLS_TOTAL = Counter(
    "remy_api_calls_total",
    "Total API calls",
    ["provider", "model", "call_site"],
)

# API call latency histogram
API_CALL_LATENCY = Histogram(
    "remy_api_call_latency_seconds",
    "API call latency by provider",
    ["provider"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60, 120],
)

# Token usage histograms
CONTEXT_TOKENS = Histogram(
    "remy_context_tokens",
    "Input token count per request",
    buckets=[500, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 150000],
)

OUTPUT_TOKENS = Histogram(
    "remy_output_tokens",
    "Output token count per request",
    buckets=[50, 100, 250, 500, 1000, 2000, 4000],
)

# Tool execution metrics
TOOL_EXECUTIONS_TOTAL = Counter(
    "remy_tool_executions_total",
    "Total tool executions",
    ["tool_name"],
)

TOOL_EXECUTION_LATENCY = Histogram(
    "remy_tool_execution_latency_seconds",
    "Tool execution latency",
    ["tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
)

# Active requests gauge
ACTIVE_REQUESTS = Gauge(
    "remy_active_requests",
    "Number of requests currently being processed",
)

# Memory injection metrics
MEMORY_INJECTION_LATENCY = Histogram(
    "remy_memory_injection_latency_seconds",
    "Time spent building memory context",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2],
)

# Embedding operations
EMBEDDING_OPERATIONS_TOTAL = Counter(
    "remy_embedding_operations_total",
    "Total embedding operations",
    ["operation"],  # "encode", "search"
)

# Error counters
ERRORS_TOTAL = Counter(
    "remy_errors_total",
    "Total errors by type",
    ["error_type"],  # "api_error", "tool_error", "telegram_error"
)

# Prompt cache metrics
CACHE_HIT_RATE = Histogram(
    "remy_cache_hit_rate",
    "Prompt cache hit rate (0.0 to 1.0)",
    ["provider", "model"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

CACHE_TOKENS_SAVED = Counter(
    "remy_cache_tokens_saved_total",
    "Total tokens served from cache (cost savings)",
    ["provider", "model"],
)

# Service info
SERVICE_INFO = Info(
    "remy_service",
    "Remy service information",
)


def observe_request_timing(timing: "RequestTiming") -> None:
    """Record all phase timings from a RequestTiming object."""
    if timing.history_load_ms > 0:
        REQUEST_LATENCY.labels(phase="history_load").observe(timing.history_load_ms / 1000)
    if timing.memory_injection_ms > 0:
        REQUEST_LATENCY.labels(phase="memory_injection").observe(timing.memory_injection_ms / 1000)
        MEMORY_INJECTION_LATENCY.observe(timing.memory_injection_ms / 1000)
    if timing.ttft_ms > 0:
        REQUEST_LATENCY.labels(phase="ttft").observe(timing.ttft_ms / 1000)
        TTFT_SECONDS.observe(timing.ttft_ms / 1000)
    if timing.tool_execution_ms > 0:
        REQUEST_LATENCY.labels(phase="tool_execution").observe(timing.tool_execution_ms / 1000)
    if timing.streaming_ms > 0:
        REQUEST_LATENCY.labels(phase="streaming").observe(timing.streaming_ms / 1000)
    if timing.persistence_ms > 0:
        REQUEST_LATENCY.labels(phase="persistence").observe(timing.persistence_ms / 1000)


def increment_api_call(
    provider: str,
    model: str,
    call_site: str,
    latency_ms: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record an API call with associated metrics."""
    API_CALLS_TOTAL.labels(provider=provider, model=model, call_site=call_site).inc()
    if latency_ms > 0:
        API_CALL_LATENCY.labels(provider=provider).observe(latency_ms / 1000)
    if input_tokens > 0:
        CONTEXT_TOKENS.observe(input_tokens)
    if output_tokens > 0:
        OUTPUT_TOKENS.observe(output_tokens)


def record_tool_execution(tool_name: str, latency_ms: int) -> None:
    """Record a tool execution."""
    TOOL_EXECUTIONS_TOTAL.labels(tool_name=tool_name).inc()
    if latency_ms > 0:
        TOOL_EXECUTION_LATENCY.labels(tool_name=tool_name).observe(latency_ms / 1000)


def record_error(error_type: str) -> None:
    """Record an error occurrence."""
    ERRORS_TOTAL.labels(error_type=error_type).inc()


def set_service_info(version: str = "1.0", environment: str = "local") -> None:
    """Set service metadata."""
    SERVICE_INFO.info({"version": version, "environment": environment})


def observe_cache_hit_rate(
    provider: str,
    model: str,
    cache_hit_rate: float,
    cache_read_tokens: int = 0,
) -> None:
    """Record cache hit rate and tokens saved from caching."""
    CACHE_HIT_RATE.labels(provider=provider, model=model).observe(cache_hit_rate)
    if cache_read_tokens > 0:
        CACHE_TOKENS_SAVED.labels(provider=provider, model=model).inc(cache_read_tokens)
