# Verification

Checked on 2026-10-12 on macOS arm64 with Python 3.12.13 and Node 24.14.0.

## Source versions

- ZCode source tag `v3.15.1`, commit `aac47556`. The standalone agent CLI reports
  `0.16.9`, independently of the product source version.
- Published Omnigent `0.17.0`.
- Omnigent `0.18.0.dev0` from upstream main, commit `87f6f08b4`.

GitHub's latest release page still points at ZCode `v3.14.3`. The newer source tag
exists and was built locally for these checks.

## Results

- Omnigent 0.17.0: 53 plugin checks passed, including 10 real-CLI integration cases.
- Omnigent 0.18.0.dev0: the same 53 checks passed against unmodified upstream main.
- ZCode's stream-json and headless-workflow contract suites: 81 checks passed.
- Ruff lint and formatting checks passed. Wheel and source archive builds passed.

Both Omnigent runs reported a Starlette TestClient deprecation warning. No test
failed. The normal CI matrix covers Linux and macOS with Python 3.12 and 3.13;
the real-CLI workflow is available through manual dispatch.

## What the tests exercise

The real-CLI suite uses an isolated vendor home and a local OpenAI-compatible
streaming provider. It launches the built ZCode executable through this plugin.
The model replies are deterministic; file reads and writes execute ZCode's real
tools. No Z.ai account is used, and no credential-store contents are read.

Coverage includes text, reasoning, usage, vendor session resume, successful and
failed tools, file and image attachment delivery, cache cleanup, cancellation,
timeout, workflow mode selection, and two turns through the harness HTTP app.

The workflow checks verify mode acceptance and tool exposure. They do not execute
a multi-agent workflow to completion. Z.ai OAuth, subscription quotas, billed
requests, model quality, and the browser UI require a vendor-account smoke test.

## Limitation audit

| Previous limitation | ZCode 3.15.1 evidence | Plugin result |
| --- | --- | --- |
| No model override | The strict CLI argument parser has no model option. | Still rejected; model belongs to vendor configuration. |
| No approval channel | Headless broker denies interactive approvals except its explicit CreateWorkflow allowance. | Still yolo-only; no Omnigent approval cards. |
| No dynamic workflows | CLI accepts `--workflow-mode disabled`, `onDemand`, and `alwaysOn`. | Added optional workflow mode forwarding. |
| No MCP | ZCode has MCP configuration and `/mcp` commands. | ZCode-managed MCP is available; no Omnigent MCP bridge. |
| No resume after restart | CLI resumes persisted vendor sessions with `--resume`. | Plugin mapping remains process-local. |
| No compaction | ZCode has `/compact` and persisted compaction metadata. | No dedicated Omnigent compaction event forwarding. |
| No cost reporting | Stream summary reports usage, while context cost is null in the mapper. | Token usage only; no dollar cost. |

Authoritative source files at the tested tag:

- [CLI arguments](https://github.com/zai-org/zcode/blob/v3.15.1/apps/zcode-cli/packages/cli/src/arguments.ts)
- [Print-mode execution](https://github.com/zai-org/zcode/blob/v3.15.1/apps/zcode-cli/packages/cli/src/prompt-command.ts)
- [Headless permission broker and workflow events](https://github.com/zai-org/zcode/blob/v3.15.1/apps/zcode-cli/packages/cli/src/headless-workflow.ts)
- [Workflow modes](https://github.com/zai-org/zcode/blob/v3.15.1/apps/zcode-cli/packages/cli/src/workflow-mode.ts)
- [Event mapper](https://github.com/zai-org/zcode/blob/v3.15.1/apps/zcode-cli/packages/bootstrap/src/zcode-protocol/session-mapper.ts)

## Repeat the checks

Build the ZCode tag using the README instructions. From the plugin checkout:

```bash
ZCODE_TEST_CLI=/absolute/path/to/zcode/apps/zcode-cli/packages/cli/dist/zcode.cjs \
ZCODE_TEST_SOURCE=/absolute/path/to/zcode \
uv run pytest
```

The real-CLI cases skip when `ZCODE_TEST_CLI` is absent. The normal suite always
checks the executor and registered harness using a fake executable.
