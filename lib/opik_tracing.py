import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_ENABLED = False
_TRACER = None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = float(str(raw).strip())
    except Exception:
        return default
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


def init_opik_tracing(service_name: str = "dcai-app") -> bool:
    global _INITIALIZED, _ENABLED, _TRACER
    if _INITIALIZED:
        return _ENABLED
    with _INIT_LOCK:
        if _INITIALIZED:
            return _ENABLED
        _INITIALIZED = True

        enabled = _env_flag("OPIK_TRACE_ENABLED", default=False)
        if not enabled:
            _ENABLED = False
            return False

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        except Exception as err:
            print(f"> WARNING: OPIK tracing disabled; OpenTelemetry import failed: {err}")
            _ENABLED = False
            return False

        endpoint = (os.getenv("OPIK_OTLP_ENDPOINT", "http://otel-collector:4317") or "").strip()
        insecure = _env_flag("OPIK_OTLP_INSECURE", default=endpoint.startswith("http://"))
        sample_rate = _env_float("OPIK_TRACE_SAMPLE_RATE", 1.0)
        env_name = (os.getenv("OPIK_ENV", os.getenv("ENV", "local")) or "local").strip()
        project_name = (os.getenv("OPIK_PROJECT_NAME", "knva-nifty") or "knva-nifty").strip()
        svc_name = (os.getenv("OPIK_SERVICE_NAME", service_name) or service_name).strip()

        try:
            resource = Resource.create(
                {
                    "service.name": svc_name,
                    "deployment.environment": env_name,
                    "opik.project.name": project_name,
                }
            )
            provider = TracerProvider(
                resource=resource,
                sampler=ParentBased(TraceIdRatioBased(sample_rate)),
            )
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            _TRACER = trace.get_tracer("dcai.opik")
            _ENABLED = True
            print(
                f"> OPIK tracing enabled: endpoint={endpoint}, service={svc_name}, "
                f"project={project_name}, sample_rate={sample_rate}"
            )
        except Exception as err:
            print(f"> WARNING: OPIK tracing disabled; exporter init failed: {err}")
            _TRACER = None
            _ENABLED = False

        return _ENABLED


def is_enabled() -> bool:
    return _ENABLED


def get_tracer(name: str = "dcai.opik"):
    try:
        from opentelemetry import trace
    except Exception:
        return None
    if _TRACER is not None:
        return _TRACER
    return trace.get_tracer(name)


def _set_span_attrs(span, attributes: Optional[Dict[str, Any]]) -> None:
    if span is None or not attributes:
        return
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, str(value))


@contextmanager
def start_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    if not _ENABLED:
        yield None
        return
    tracer = get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as span:
        _set_span_attrs(span, attributes)
        yield span


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    if not _ENABLED:
        return
    try:
        from opentelemetry import trace
    except Exception:
        return
    span = trace.get_current_span()
    if not span:
        return
    if attributes:
        safe_attrs = {}
        for key, value in attributes.items():
            if value is None:
                continue
            safe_attrs[key] = value if isinstance(value, (str, bool, int, float)) else str(value)
        span.add_event(name, attributes=safe_attrs)
    else:
        span.add_event(name)


def current_trace_id_hex() -> str:
    if not _ENABLED:
        return ""
    try:
        from opentelemetry import trace
    except Exception:
        return ""
    span = trace.get_current_span()
    if not span:
        return ""
    ctx = span.get_span_context()
    if not ctx or not getattr(ctx, "trace_id", 0):
        return ""
    return format(ctx.trace_id, "032x")
