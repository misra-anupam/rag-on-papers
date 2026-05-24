import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram, start_http_server


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_tracing(service_name: str = "rag-medical", otlp_endpoint: str = "") -> None:
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "rag-medical") -> trace.Tracer:
    return trace.get_tracer(name)


def start_metrics_server(port: int = 8000) -> None:
    start_http_server(port)


# ── Prometheus metrics ────────────────────────────────────────────────────────

papers_fetched = Counter("papers_fetched_total", "Total papers fetched", ["source"])
papers_parsed = Counter("papers_parsed_total", "Total papers parsed", ["status"])
chunks_indexed = Counter("chunks_indexed_total", "Total chunks indexed into Qdrant")
embedding_latency = Histogram("embedding_latency_seconds", "Dense embedding API latency")
retrieval_latency = Histogram(
    "retrieval_latency_seconds", "Retrieval latency per strategy", ["strategy"]
)
rerank_latency = Histogram("rerank_latency_seconds", "RRF + MMR rerank latency")
agent_run_latency = Histogram("agent_run_latency_seconds", "Full CrewAI crew run latency")
openrouter_tokens = Counter(
    "openrouter_tokens_total", "OpenRouter tokens consumed", ["model", "type"]
)
qdrant_collection_size = Gauge(
    "qdrant_points_total", "Current number of points in Qdrant collection"
)
figure_describe_latency = Histogram(
    "figure_describe_latency_seconds", "LLM figure description latency"
)


# Initialise logging immediately on import
configure_logging()
log = structlog.get_logger()
