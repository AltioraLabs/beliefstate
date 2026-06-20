"""OpenTelemetry observability integration for BeliefState.

Provides optional instrumentation for monitoring belief tracking pipeline:
- Belief extraction latency
- Contradiction detection latency
- Belief resolution timing
- Store operations (add, search, prune)
- Adapter calls (generate, embeddings)

Usage:
    from beliefstate.observability import setup_otel

    # Setup with default configuration
    setup_otel()

    # Or with custom service name
    setup_otel(service_name="my-belief-tracker")

    # Or disable entirely
    setup_otel(enabled=False)
"""

import logging
from typing import Any, Optional, Callable, Coroutine, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

# Optional imports - gracefully degrade if not available
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.api.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.debug(
        "OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
    )

T = TypeVar("T")

# Global state
_tracer: Optional[Any] = None
_meter: Optional[Any] = None
_otel_enabled = False


def setup_otel(
    enabled: bool = True,
    service_name: str = "beliefstate",
    otel_exporter_otlp_endpoint: str = "http://localhost:4317",
) -> None:
    """Initialize OpenTelemetry for BeliefState.

    Args:
        enabled: Whether to enable OTel instrumentation
        service_name: Service name for traces/metrics
        otel_exporter_otlp_endpoint: OTLP gRPC exporter endpoint (Jaeger, DataDog, etc.)

    Example:
        # Enable with defaults (sends to localhost:4317)
        setup_otel()

        # Disable
        setup_otel(enabled=False)

        # Custom endpoint (e.g., Datadog)
        setup_otel(otel_exporter_otlp_endpoint="http://datadog-agent:4317")
    """
    global _tracer, _meter, _otel_enabled

    _otel_enabled = enabled

    if not enabled:
        logger.info("OpenTelemetry instrumentation disabled")
        return

    if not OTEL_AVAILABLE:
        logger.warning(
            "OpenTelemetry not available. Install with: "
            "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        _otel_enabled = False
        return

    try:
        # Setup tracer
        otlp_exporter = OTLPSpanExporter(endpoint=otel_exporter_otlp_endpoint)
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer(__name__)

        # Setup meter
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=otel_exporter_otlp_endpoint)
        )
        meter_provider = MeterProvider(metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter(__name__)

        logger.info(
            f"OpenTelemetry initialized: service={service_name}, endpoint={otel_exporter_otlp_endpoint}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
        _otel_enabled = False


def trace_sync(
    operation_name: str, attributes: Optional[dict[str, Any]] = None
) -> Callable[..., Any]:
    """Decorator to trace synchronous functions.

    Args:
        operation_name: Name of the operation for tracing
        attributes: Optional dict of attributes to attach to span

    Example:
        @trace_sync("belief_extraction", {"model": "gpt-4"})
        def extract_beliefs(text):
            return ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _otel_enabled or _tracer is None:
                return func(*args, **kwargs)

            with _tracer.start_as_current_span(operation_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


def trace_async(
    operation_name: str, attributes: Optional[dict[str, Any]] = None
) -> Callable[..., Any]:
    """Decorator to trace async functions.

    Args:
        operation_name: Name of the operation for tracing
        attributes: Optional dict of attributes to attach to span

    Example:
        @trace_async("contradiction_detection", {"session_id": "user-123"})
        async def detect_contradictions(beliefs):
            return ...
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if not _otel_enabled or _tracer is None:
                return await func(*args, **kwargs)

            with _tracer.start_as_current_span(operation_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    if OTEL_AVAILABLE:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


class BeliefTrackerMetrics:
    """Metrics for BeliefState operations.

    Tracks:
    - Beliefs extracted per call
    - Contradictions detected
    - Store operation latencies
    - Adapter call latencies
    """

    def __init__(self) -> None:
        if not _otel_enabled or _meter is None:
            self.enabled = False
            return

        self.enabled = True

        # Counters
        self.beliefs_extracted = _meter.create_counter(
            name="beliefstate.beliefs_extracted",
            description="Number of beliefs extracted",
            unit="1",
        )

        self.contradictions_detected = _meter.create_counter(
            name="beliefstate.contradictions_detected",
            description="Number of contradictions detected",
            unit="1",
        )

        self.beliefs_deduplicated = _meter.create_counter(
            name="beliefstate.beliefs_deduplicated",
            description="Number of beliefs deduped due to entailment",
            unit="1",
        )

        # Histograms (latency metrics)
        self.extraction_latency = _meter.create_histogram(
            name="beliefstate.extraction_latency_ms",
            description="Latency of belief extraction in milliseconds",
            unit="ms",
        )

        self.detection_latency = _meter.create_histogram(
            name="beliefstate.detection_latency_ms",
            description="Latency of contradiction detection in milliseconds",
            unit="ms",
        )

        self.store_search_latency = _meter.create_histogram(
            name="beliefstate.store_search_latency_ms",
            description="Latency of belief store searches in milliseconds",
            unit="ms",
        )

        self.adapter_generate_latency = _meter.create_histogram(
            name="beliefstate.adapter_generate_latency_ms",
            description="Latency of LLM generation calls in milliseconds",
            unit="ms",
        )

        self.adapter_embedding_latency = _meter.create_histogram(
            name="beliefstate.adapter_embedding_latency_ms",
            description="Latency of embedding generation in milliseconds",
            unit="ms",
        )

        # Gauges (current state)
        self.beliefs_in_store = _meter.create_observable_gauge(
            name="beliefstate.beliefs_in_store",
            description="Current number of beliefs in store",
            unit="1",
        )

    def record_beliefs_extracted(self, count: int) -> None:
        """Record number of extracted beliefs."""
        if self.enabled:
            self.beliefs_extracted.add(count)

    def record_contradiction(self) -> None:
        """Record a detected contradiction."""
        if self.enabled:
            self.contradictions_detected.add(1)

    def record_deduplication(self) -> None:
        """Record a deduped belief."""
        if self.enabled:
            self.beliefs_deduplicated.add(1)

    def record_extraction_latency(self, latency_ms: float) -> None:
        """Record extraction latency in milliseconds."""
        if self.enabled:
            self.extraction_latency.record(latency_ms)

    def record_detection_latency(self, latency_ms: float) -> None:
        """Record detection latency in milliseconds."""
        if self.enabled:
            self.detection_latency.record(latency_ms)

    def record_store_search_latency(self, latency_ms: float) -> None:
        """Record store search latency in milliseconds."""
        if self.enabled:
            self.store_search_latency.record(latency_ms)

    def record_adapter_generate_latency(self, latency_ms: float) -> None:
        """Record adapter generation latency in milliseconds."""
        if self.enabled:
            self.adapter_generate_latency.record(latency_ms)

    def record_adapter_embedding_latency(self, latency_ms: float) -> None:
        """Record adapter embedding latency in milliseconds."""
        if self.enabled:
            self.adapter_embedding_latency.record(latency_ms)
