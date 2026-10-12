# omnigent-zcode

Community [ZCode](https://github.com/zai-org/zcode) harness for
[Omnigent](https://github.com/omnigent-ai/omnigent). Runs ZCode's headless
`stream-json` mode, with one CLI process per turn.

## Install

Requires Python 3.12 or later, Omnigent 0.17, and the ZCode CLI.
The adapter targets ZCode 3.14.3. Source builds of that release require Node 24.
Install ZCode using its upstream instructions, then sign in:

```bash
zcode login
```

If Omnigent is installed as a uv tool, install the plugin into that tool:

```bash
uv tool inject omnigent git+https://github.com/anxkhn/omnigent-zcode.git
omnigent run --harness zcode -p "Say pong"
```

For an existing Python virtual environment:

```bash
uv pip install git+https://github.com/anxkhn/omnigent-zcode.git
```

Restart any running Omnigent server and host after installing the plugin.
The `zcode` harness and `z-code` alias register automatically. Install the plugin
on each machine running an Omnigent server or host that needs to use ZCode.

The package is available from GitHub. It has not been published to PyPI.

## Configure

If `zcode` is outside the host's `PATH`, set its executable in Omnigent config:

```yaml
harness:
  zcode:
    command: /absolute/path/to/zcode
```

`OMNIGENT_ZCODE_PATH` takes precedence over that setting.
Omnigent 0.17's community readiness probe still checks `zcode` on `PATH`.
Keep that command available to the host even when using an executable override.
ZCode owns login and model selection. Credentials stay in
`~/.zcode/v2/credentials.json`; `ZCODE_DATA_BASE_DIR` changes the base directory.
For Coding Plan API-key login, use `/login zai-coding-plan-api-key <key>` in
ZCode's TUI. Do not set `executor.auth` or a model override in Omnigent.

```bash
omnigent run examples/zcode_hello.yaml -p "Say pong"
```

The web harness picker gets the ZCode row through the community registry.
Core readiness checks CLI availability. The plugin API has no custom credential
probe or custom CLI setup-menu row, so ZCode reports login failures at runtime.
Omnigent 0.17's startup header and `/model` readout can show an unrelated global
provider default. ZCode still uses its own credentials and model; those displays
do not change the subprocess configuration.

## Supported behavior

- Text, reasoning, tool events and token usage stream into Omnigent.
- Follow-up turns use ZCode's `--resume` session ID while the executor is alive.
- Cancel and timeout terminate the CLI process tree.
- File and image data URIs use a session attachment cache outside the workspace.
  Closing the session removes that cache. Local paths must resolve inside the
  workspace; remote attachment URLs are unsupported.
- The subprocess receives Omnigent's filtered base environment, `ZCODE_*`,
  `ZAI_OAUTH_ORIGIN`, `ZAI_BUSINESS_BASE_URL`, `ZAI_OAUTH_CLIENT_ID`, and
  `BIGMODEL_API_BASE_URL`. Explicit `os_env.sandbox.env_passthrough` entries
  permit other variables.

## Limits

Only `yolo` print mode is supported. ZCode executes its own tools, and this
adapter reports those tool events. It does not enforce Omnigent tool policies
or answer approval requests. Configure `os_env.sandbox` for OS-level isolation.
An active sandbox requires explicit access to ZCode's credential, provider
configuration and session-storage paths. ZCode's tools share those grants.

There is no model override, terminal wrapper, MCP tool bridge, history replay
after an executor restart, dollar-cost reporting, or dynamic workflow support.
The first successful turn includes the system prompt; subsequent turns resume
the vendor session. Forked sessions do not inherit ZCode history.

## Development

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
```

Tests use a fake CLI and need no Z.ai account. To verify the real integration,
sign in to ZCode, run `omnigent run --harness zcode`, ask it to remember a short
phrase, then ask it to repeat that phrase in a follow-up turn. Ask it to read a
workspace file and check the tool event. Start a longer task and cancel it.

From this checkout, use `uv run omnigent run --harness zcode` to run the local
development environment. CI builds wheels and source archives on Linux and
macOS. The package workflow also provides downloadable artifacts on manual runs.

## Origin

Extracted from [Omnigent PR #8470](https://github.com/omnigent-ai/omnigent/pull/8470)
following the maintainers' recommendation to maintain ZCode support as a
community harness. Related upstream issue:
[#4865](https://github.com/omnigent-ai/omnigent/issues/4865).

Licensed under Apache-2.0.
