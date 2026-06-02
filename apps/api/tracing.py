from __future__ import annotations

import structlog

_log = structlog.get_logger(__name__)


def setup_mlflow_tracing(tracking_uri: str, experiment_name: str) -> None:
    """Configure MLflow tracing for LangChain/LangGraph.

    Call once at startup when MLFLOW_TRACKING_URI is set. Skipped silently when
    not set — MLflow is optional observability, not a required service.
    """
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    mlflow.langchain.autolog(log_traces=True)

    # MLflow 3.x doesn't implement on_interrupt; LangGraph fires it on every HITL interrupt.
    # Guard with hasattr so this self-removes when MLflow adds the method.
    try:
        from mlflow.langchain.langchain_tracer import MlflowLangchainTracer

        for _cb in ("on_interrupt", "on_resume"):
            if not hasattr(MlflowLangchainTracer, _cb):
                setattr(MlflowLangchainTracer, _cb, lambda self, *args, **kwargs: None)
    except ImportError:
        pass

    _log.info("mlflow_tracing_enabled", tracking_uri=tracking_uri, experiment=experiment_name)
