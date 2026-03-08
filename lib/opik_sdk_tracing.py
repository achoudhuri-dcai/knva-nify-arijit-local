import os
import contextvars
from contextlib import contextmanager
from typing import Any, Dict, Optional

_INITIALIZED = False
_ENABLED = False
_CLIENT = None
_PROJECT_NAME = None

_CURRENT_TRACE = contextvars.ContextVar("opik_current_trace", default=None)
_CURRENT_SPAN_STACK = contextvars.ContextVar("opik_current_span_stack", default=())


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _sanitize_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            sv = _sanitize_json_value(v)
            if sv is not None:
                out[str(k)] = sv
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(v) for v in value]
    return str(value)


def init_opik_sdk() -> bool:
    global _INITIALIZED, _ENABLED, _CLIENT, _PROJECT_NAME
    if _INITIALIZED:
        return _ENABLED
    _INITIALIZED = True

    if not _env_flag("OPIK_SDK_TRACE_ENABLED", default=False):
        _ENABLED = False
        return False

    try:
        import opik
    except Exception as err:
        print(f"> WARNING: Opik SDK tracing disabled; import failed: {err}")
        _ENABLED = False
        return False

    host = (os.getenv("OPIK_SDK_HOST", "http://opik-backend-1:8080") or "").strip()
    project = (os.getenv("OPIK_SDK_PROJECT_NAME", "Default Project") or "Default Project").strip()
    workspace = (os.getenv("OPIK_SDK_WORKSPACE", "default") or "default").strip()

    try:
        _CLIENT = opik.Opik(project_name=project, workspace=workspace, host=host)
        _PROJECT_NAME = project
        _ENABLED = True
        print(f"> Opik SDK tracing enabled: host={host}, workspace={workspace}, project={project}")
    except Exception as err:
        print(f"> WARNING: Opik SDK tracing disabled; client init failed: {err}")
        _CLIENT = None
        _PROJECT_NAME = None
        _ENABLED = False
    return _ENABLED


def is_enabled() -> bool:
    return _ENABLED and _CLIENT is not None


def project_name() -> str:
    return _PROJECT_NAME or ""


def current_trace():
    return _CURRENT_TRACE.get()


def current_trace_id() -> str:
    trace_obj = current_trace()
    if trace_obj is None:
        return ""
    return str(getattr(trace_obj, "id", "") or "")


@contextmanager
def start_trace(
    name: str,
    *,
    input_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
    thread_id: Optional[str] = None,
):
    if not is_enabled():
        yield None
        return

    trace_obj = _CLIENT.trace(
        name=name,
        input=_sanitize_json_value(input_data) if input_data is not None else None,
        metadata=_sanitize_json_value(metadata) if metadata is not None else None,
        tags=tags or [],
        thread_id=thread_id,
    )
    token = _CURRENT_TRACE.set(trace_obj)
    try:
        yield trace_obj
        trace_obj.end()
    except Exception as err:
        try:
            trace_obj.end(
                error_info={
                    "exception_type": type(err).__name__,
                    "message": str(err),
                }
            )
        except Exception:
            pass
        raise
    finally:
        _CURRENT_TRACE.reset(token)


@contextmanager
def start_span(
    name: str,
    *,
    span_type: str = "general",
    input_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
):
    if not is_enabled():
        yield None
        return

    trace_obj = current_trace()
    if trace_obj is None:
        # Fallback: no active trace context.
        with start_trace(name=f"{name}.trace", metadata={"autocreated": True}):
            with start_span(
                name,
                span_type=span_type,
                input_data=input_data,
                metadata=metadata,
                tags=tags,
                model=model,
                provider=provider,
            ) as nested:
                yield nested
            return

    span_stack = tuple(_CURRENT_SPAN_STACK.get())
    parent_span = span_stack[-1] if span_stack else None
    parent_span_id = getattr(parent_span, "id", None) if parent_span is not None else None

    span_obj = trace_obj.span(
        name=name,
        type=span_type,
        parent_span_id=parent_span_id,
        input=_sanitize_json_value(input_data) if input_data is not None else None,
        metadata=_sanitize_json_value(metadata) if metadata is not None else None,
        tags=tags or [],
        model=model,
        provider=provider,
    )

    token = _CURRENT_SPAN_STACK.set(span_stack + (span_obj,))
    try:
        yield span_obj
        span_obj.end()
    except Exception as err:
        try:
            span_obj.end(
                error_info={
                    "exception_type": type(err).__name__,
                    "message": str(err),
                }
            )
        except Exception:
            pass
        raise
    finally:
        _CURRENT_SPAN_STACK.reset(token)
