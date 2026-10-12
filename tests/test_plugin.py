"""Installed entry-point discovery and runner launch configuration."""

import importlib
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest
from omnigent.harness_aliases import canonicalize_harness
from omnigent.harness_plugins import (
    harness_catalog,
    harness_modules,
    plugin_state,
    spawn_env_builders,
    valid_harnesses,
)
from omnigent.inner.datamodel import OSEnvSandboxSpec, OSEnvSpec
from omnigent.spec.types import AgentSpec, ExecutorSpec

from omnigent.community.harness.zcode.spawn_env import build_spawn_env


def spec(**config) -> AgentSpec:
    return AgentSpec(
        spec_version=1,
        name="zcode-test",
        instructions="test",
        executor=ExecutorSpec(type="omnigent", config={"harness": "zcode", **config}),
    )


def test_installed_entry_point_registers_every_launch_path():
    points = importlib.metadata.entry_points(group="omnigent.community.harness")
    assert any(point.name == "zcode" for point in points)
    assert not plugin_state().load_errors
    assert "zcode" in valid_harnesses()
    assert canonicalize_harness("z-code") == "zcode"
    assert harness_modules()["z-code"] == harness_modules()["zcode"]
    module = importlib.import_module(harness_modules()["zcode"])
    assert callable(module.create_app)
    assert spawn_env_builders()["zcode"].endswith("spawn_env:build_spawn_env")
    row = next(row for row in harness_catalog() if row["id"] == "zcode")
    assert row["label"] == "ZCode"
    assert row["capabilities"]["auth"] == "own-auth"
    from omnigent.onboarding.harness_install import harness_install_spec

    assert harness_install_spec("zcode").login_args == ("login",)


def test_registration_survives_fresh_process():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from omnigent.harness_plugins import valid_harnesses; "
            "assert 'zcode' in valid_harnesses()",
        ],
        cwd=Path.home(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_spawn_builder_round_trips_config(tmp_path, monkeypatch):
    monkeypatch.setattr("omnigent.onboarding.provider_config.load_config", lambda: {})
    agent = spec(mode="yolo", disallowed_tools=["shell"], workflow_mode="onDemand")
    agent.os_env = OSEnvSpec(
        type="caller_process",
        cwd=str(tmp_path),
        sandbox=OSEnvSandboxSpec(type="none", env_passthrough=["CUSTOM_TOKEN"]),
    )
    env = build_spawn_env(agent, cwd=tmp_path)
    assert env["HARNESS_ZCODE_CWD"] == str(tmp_path)
    assert env["HARNESS_ZCODE_MODE"] == "yolo"
    assert env["HARNESS_ZCODE_WORKFLOW_MODE"] == "onDemand"
    assert json.loads(env["HARNESS_ZCODE_DISALLOWED_TOOLS"]) == ["shell"]
    assert json.loads(env["HARNESS_ZCODE_OS_ENV"])["sandbox"]["env_passthrough"] == ["CUSTOM_TOKEN"]


def test_configured_command_and_environment_precedence(monkeypatch):
    monkeypatch.delenv("OMNIGENT_ZCODE_PATH", raising=False)
    monkeypatch.setattr(
        "omnigent.onboarding.provider_config.load_config",
        lambda: {"harness": {"zcode": {"command": "/custom/zcode"}}},
    )
    assert build_spawn_env(spec())["OMNIGENT_ZCODE_PATH"] == "/custom/zcode"
    monkeypatch.setenv("OMNIGENT_ZCODE_PATH", "/ambient/zcode")
    assert build_spawn_env(spec())["OMNIGENT_ZCODE_PATH"] == "/ambient/zcode"


@pytest.mark.parametrize("harness", ["zcode", "z-code"])
def test_runner_dispatches_registered_spawn_builder(harness, tmp_path, monkeypatch):
    from omnigent.runner.app import _build_spawn_env_from_spec

    monkeypatch.setattr("omnigent.onboarding.provider_config.load_config", lambda: {})
    env = _build_spawn_env_from_spec(spec(), harness, cwd=tmp_path)
    assert env is not None
    assert env["HARNESS_ZCODE_CWD"] == str(tmp_path)
    assert env["OMNIGENT_ZCODE_PATH"]


def test_executor_environment_drops_unrelated_provider_keys(monkeypatch):
    from omnigent.community.harness.zcode.zcode_executor import ZCodeExecutor

    monkeypatch.setenv("OPENAI_API_KEY", "other-provider")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "other-provider")
    monkeypatch.setenv("ZCODE_DATA_BASE_DIR", "/vendor-home")
    monkeypatch.setenv("ZAI_OAUTH_ORIGIN", "https://example.com")
    env = ZCodeExecutor()._build_spawn_env()
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert env["ZCODE_DATA_BASE_DIR"] == "/vendor-home"
    assert env["ZAI_OAUTH_ORIGIN"] == "https://example.com"


def test_harness_decodes_sandbox_passthrough(monkeypatch):
    from omnigent.community.harness.zcode.zcode_harness import _resolve_os_env

    monkeypatch.setenv(
        "HARNESS_ZCODE_OS_ENV",
        json.dumps(
            {
                "type": "caller_process",
                "sandbox": {
                    "type": "none",
                    "env_passthrough": ["CUSTOM_TOKEN"],
                },
            }
        ),
    )
    assert _resolve_os_env().sandbox.env_passthrough == ["CUSTOM_TOKEN"]


@pytest.mark.parametrize("harness", ["zcode", "z-code"])
def test_example_spec_accepts_plugin_harness(harness, tmp_path):
    from omnigent.spec import load

    example = Path(__file__).parents[1] / "examples" / "zcode_hello.yaml"
    path = tmp_path / "agent.yaml"
    path.write_text(example.read_text().replace("harness: zcode", f"harness: {harness}"))
    assert load(path).executor.harness_kind == "zcode"
