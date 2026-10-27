import pytest


@pytest.fixture(autouse=True)
def isolated_agent_environment(monkeypatch):
    """Unit/integration tests never consume a developer's live credentials."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_MODE", "assist")
