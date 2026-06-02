from __future__ import annotations

"""Unit tests for MLflow tracing setup.

Verifies:
- When MLFLOW_TRACKING_URI is absent, setup_mlflow_tracing is never called.
- When MLFLOW_TRACKING_URI is set, setup_mlflow_tracing is called with the
  correct arguments.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestMlflowTracingSetup:
    """MLflow tracing is only activated when MLFLOW_TRACKING_URI is set."""

    def test_setup_not_called_when_uri_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MLFLOW_TRACKING_URI is absent the tracing setup is never invoked."""
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        monkeypatch.delenv("MLFLOW_EXPERIMENT_NAME", raising=False)

        with patch("apps.api.tracing.setup_mlflow_tracing") as mock_setup:
            # Simulate what main.py lifespan does
            mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
            if mlflow_uri:
                from apps.api.tracing import setup_mlflow_tracing
                experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "business-decision-os")
                setup_mlflow_tracing(mlflow_uri, experiment_name)

            mock_setup.assert_not_called()

    def test_setup_called_with_correct_args_when_uri_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When MLFLOW_TRACKING_URI is set, setup_mlflow_tracing is called with correct args."""
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "bdos-test")

        with patch("apps.api.tracing.setup_mlflow_tracing") as mock_setup:
            # Simulate what main.py lifespan does
            mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
            if mlflow_uri:
                from apps.api.tracing import setup_mlflow_tracing
                experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "business-decision-os")
                setup_mlflow_tracing(mlflow_uri, experiment_name)

            mock_setup.assert_called_once_with("http://mlflow:5000", "bdos-test")

    def test_setup_uses_default_experiment_name_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default experiment name is 'business-decision-os' when env var is absent."""
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        monkeypatch.delenv("MLFLOW_EXPERIMENT_NAME", raising=False)

        with patch("apps.api.tracing.setup_mlflow_tracing") as mock_setup:
            mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
            if mlflow_uri:
                from apps.api.tracing import setup_mlflow_tracing
                experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "business-decision-os")
                setup_mlflow_tracing(mlflow_uri, experiment_name)

            mock_setup.assert_called_once_with("http://mlflow:5000", "business-decision-os")

    def test_setup_mlflow_tracing_calls_mlflow_api(self) -> None:
        """setup_mlflow_tracing calls mlflow.set_tracking_uri and set_experiment."""
        mock_mlflow = MagicMock()
        # mlflow.langchain must be a MagicMock too so .autolog() works
        mock_mlflow.langchain = MagicMock()

        with patch.dict("sys.modules", {"mlflow": mock_mlflow, "mlflow.langchain": mock_mlflow.langchain}):
            from apps.api.tracing import setup_mlflow_tracing

            setup_mlflow_tracing("http://mlflow:5000", "my-experiment")

            mock_mlflow.set_tracking_uri.assert_called_once_with("http://mlflow:5000")
            mock_mlflow.set_experiment.assert_called_once_with("my-experiment")
            mock_mlflow.langchain.autolog.assert_called_once_with(log_traces=True)
