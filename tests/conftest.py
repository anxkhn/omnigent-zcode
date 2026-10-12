"""Keep test attachments and configuration outside the user's Omnigent state."""

import pytest


@pytest.fixture(autouse=True)
def isolated_state(tmp_path_factory, monkeypatch):
    state = tmp_path_factory.mktemp("omnigent-state")
    monkeypatch.setenv("OMNIGENT_DATA_DIR", str(state / "data"))
    monkeypatch.setenv("OMNIGENT_CONFIG_HOME", str(state / "config"))
