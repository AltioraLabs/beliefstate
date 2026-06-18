# OpenTelemetry Integration Guide

BeliefState includes optional OpenTelemetry instrumentation for comprehensive observability across the belief tracking pipeline.

## Quick Start

### 1. Install Dependencies

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### 2. Initialize in Your Application

```python
from beliefstate import setup_otel, BeliefTracker, TrackerConfig

# Setup OTel at application startup
setup_otel(service_name="my-belief-tracker")

# Create tracker as normal
config = TrackerConfig()
tracker = BeliefTracker(config)
```

### 3. View Traces in Your Backend

Configure your OTel collector endpoint:

```python
# Default: http://localhost:4317 (Jaeger, local development)
setup_otel(otel_exporter_otlp_endpoint="http://localhost:4317")

# DataDog
setup_otel(otel_exporter_otlp_endpoint="http://datadog-agent:4317")

# Grafana Loki/Tempo
setup_otel(otel_exporter_otlp_endpoint="http://tempo:4317")
```

## Metrics & Traces

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `beliefstate.beliefs_extracted` | Counter | Number of beliefs extracted per call |
| `beliefstate.contradictions_detected` | Counter | Number of contradictions found |
| `beliefstate.beliefs_deduplicated` | Counter | Number of beliefs removed via entailment |
| `beliefstate.extraction_latency_ms` | Histogram | Extraction operation latency |
| `beliefstate.detection_latency_ms` | Histogram | Contradiction detection latency |
| `beliefstate.store_search_latency_ms` | Histogram | Store vector search latency |
| `beliefstate.adapter_generate_latency_ms` | Histogram | LLM generation call latency |
| `beliefstate.adapter_embedding_latency_ms` | Histogram | Embedding API call latency |

### Trace Spans

Key operations are traced:
- **belief_extraction**: Text → beliefs conversion
- **contradiction_detection**: Semantic comparison of beliefs
- **belief_resolution**: Conflict handling
- **store_operations**: Add, search, prune operations
- **adapter_calls**: LLM generation and embeddings

## Usage Examples

### Manual Tracing

Use decorators to trace custom functions:

```python
from beliefstate import trace_async, trace_sync

@trace_async("my_operation", {"user_id": "user-123"})
async def my_async_function():
    return "result"

@trace_sync("sync_operation")
def my_sync_function():
    return "result"
```

### Metrics Collection

```python
from beliefstate import BeliefTrackerMetrics

metrics = BeliefTrackerMetrics()

# Record events
metrics.record_beliefs_extracted(5)
metrics.record_contradiction()
metrics.record_extraction_latency(150.0)  # milliseconds
metrics.record_adapter_generate_latency(500.0)
```

### Disabling OTel

To disable OTel without uninstalling dependencies:

```python
from beliefstate import setup_otel

setup_otel(enabled=False)
```

## Integration with Popular Platforms

### Jaeger (Local Development)

1. Start Jaeger locally:
```bash
docker run -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
```

2. Initialize BeliefState:
```python
setup_otel(otel_exporter_otlp_endpoint="http://localhost:4317")
```

3. View traces: http://localhost:16686

### DataDog

```python
setup_otel(
    otel_exporter_otlp_endpoint="http://datadog-agent:4317",
    service_name="beliefstate-prod"
)
```

Set environment variables:
```bash
DD_SERVICE=beliefstate-prod
DD_ENV=production
DD_TRACE_ENABLED=true
```

### Grafana Tempo + Prometheus

```python
setup_otel(
    otel_exporter_otlp_endpoint="http://tempo:4317",
    service_name="beliefstate"
)
```

Configure Tempo as a data source in Grafana to query traces.

### AWS X-Ray

```python
from opentelemetry.exporter.aws_xray.trace_exporter import XRayExporter

setup_otel(
    otel_exporter_otlp_endpoint="http://localhost:2000"
)
```

## Environment Variables

OTel respects standard environment variables:

```bash
# Exporter endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317

# Service name
OTEL_SERVICE_NAME=beliefstate

# Sample rate (0.0-1.0)
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # Sample 10% of traces

# Batch processor settings
OTEL_BSP_MAX_QUEUE_SIZE=512
OTEL_BSP_SCHEDULE_DELAY=5000  # milliseconds
```

## Performance Considerations

- **OTel Overhead**: ~5-15% for span creation and export
- **Sampling**: Use sampling in production to reduce volume (see env vars)
- **Batching**: Spans are batched (default 512 spans) before export
- **Optional**: OTel is fully optional - zero overhead if `setup_otel(enabled=False)`

## Troubleshooting

### No traces appearing in backend

1. Verify OTel exporter is reachable:
```python
setup_otel(otel_exporter_otlp_endpoint="http://your-collector:4317")
```

2. Check logs for errors:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

3. Verify collector is running and configured to accept OTLP

### High latency

- Reduce sampling rate via `OTEL_TRACES_SAMPLER_ARG`
- Increase batch size: `OTEL_BSP_MAX_QUEUE_SIZE`
- Use gRPC protocol (default) instead of HTTP

## Example: Full Integration

```python
import asyncio
from beliefstate import (
    setup_otel,
    BeliefTracker,
    TrackerConfig,
    OpenAIAdapter,
    BeliefTrackerMetrics,
)

# 1. Setup observability at startup
setup_otel(
    service_name="my-app",
    otel_exporter_otlp_endpoint="http://localhost:4317"
)
metrics = BeliefTrackerMetrics()

# 2. Create tracker
config = TrackerConfig()
adapter = OpenAIAdapter(model="gpt-4")
tracker = BeliefTracker(config, adapter=adapter)

# 3. Use tracker normally - metrics/traces auto-recorded
@tracker.wrap
async def chat(messages):
    import openai
    client = openai.AsyncOpenAI()
    return await client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

async def main():
    tracker.set_session("user-123")
    
    # Make chat call - automatically traced and metered
    response = await chat(messages=[
        {"role": "user", "content": "Hello!"}
    ])
    
    # Manually record additional metrics
    beliefs = await tracker.get_beliefs()
    metrics.record_beliefs_extracted(len(beliefs))
    
    print(f"Response: {response.choices[0].message.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Next Steps

- Configure sampling for production loads
- Set up dashboards in Grafana/DataDog for key metrics
- Create alerts on high latency or error rates
- Use trace context for debugging multi-service requests
