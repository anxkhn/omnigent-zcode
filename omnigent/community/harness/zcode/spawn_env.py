"""Translate agent configuration into the ZCode harness launch environment."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnigent.spec.types import AgentSpec


def build_spawn_env(
    spec: AgentSpec, *, cwd: Path | None = None, workdir: Path | None = None
) -> dict[str, str]:
    from omnigent.errors import ErrorCode, OmnigentError
    from omnigent.harness_startup_config import resolve_harness_command
    from omnigent.onboarding.provider_config import load_config

    del workdir
    if spec.executor.auth is not None:
        raise OmnigentError(
            "The 'zcode' harness does not accept executor.auth. "
            "Use `zcode login`, or configure a Coding Plan API key in the ZCode TUI.",
            code=ErrorCode.INVALID_INPUT,
        )
    env = {
        "OMNIGENT_ZCODE_PATH": resolve_harness_command("zcode", default="zcode", cfg=load_config())
    }
    if spec.executor.model is not None:
        env["HARNESS_ZCODE_MODEL"] = spec.executor.model
    if cwd is not None:
        env["HARNESS_ZCODE_CWD"] = str(cwd)
    mode = spec.executor.config.get("mode") or spec.executor.config.get("permission_mode")
    if mode is not None:
        env["HARNESS_ZCODE_MODE"] = str(mode)
    disallowed = spec.executor.config.get("disallowed_tools")
    if isinstance(disallowed, list) and disallowed:
        env["HARNESS_ZCODE_DISALLOWED_TOOLS"] = json.dumps(disallowed)
    if spec.os_env is not None:
        env["HARNESS_ZCODE_OS_ENV"] = json.dumps(dataclasses.asdict(spec.os_env))
    return env
