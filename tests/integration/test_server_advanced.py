"""
Integration tests for advanced server routes (readyz, metrics, config, runs).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentforge.server.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestReadyz:
    """Tests for GET /api/v1/readyz."""

    def test_readyz_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/v1/readyz")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ready") is True
        assert "version" in data
        assert "checks" in data


class TestMetrics:
    """Tests for GET /api/v1/metrics."""

    def test_metrics_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/v1/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "counters" in data
        assert "gauges" in data


class TestConfig:
    """Tests for GET /api/v1/config."""

    def test_config_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/v1/config")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "server_port" in data


class TestRuns:
    """Tests for GET /api/v1/runs."""

    def test_runs_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/v1/runs")
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data
        assert "total" in data
        assert data["total"] >= 0
