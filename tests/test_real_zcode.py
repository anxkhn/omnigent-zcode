"""Opt-in integration checks against a built ZCode CLI and a local model provider."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from omnigent.inner.executor import (
    ExecutorError,
    ReasoningChunk,
    TextChunk,
    ToolCallComplete,
    ToolCallRequest,
    ToolCallStatus,
    TurnCancelled,
    TurnComplete,
)
from PIL import Image

from omnigent.community.harness.zcode.zcode_executor import ZCodeExecutor

REAL_CLI = os.environ.get("ZCODE_TEST_CLI")
pytestmark = pytest.mark.skipif(
    not REAL_CLI, reason="Set ZCODE_TEST_CLI to a built ZCode executable"
)


@pytest.fixture
def real_zcode(tmp_path, monkeypatch):
    requests = []
    replies = []
    received = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            received.set()
            reply = replies.pop(0) if replies else {"text": "pong"}
            if reply.get("hang"):
                self.connection.settimeout(40)
                try:
                    self.connection.recv(1)
                except OSError:
                    pass
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            deltas = []
            if reply.get("reasoning"):
                deltas.append({"reasoning_content": reply["reasoning"]})
            if reply.get("tool"):
                name, args = reply["tool"]
                deltas.append(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"call-{len(requests)}",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)},
                            }
                        ]
                    }
                )
            else:
                deltas.append({"content": reply.get("text", "pong")})
            for delta in [{"role": "assistant"}, *deltas, {}]:
                finish = ("tool_calls" if reply.get("tool") else "stop") if not delta else None
                event = {
                    "id": "test",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "mock-zcode",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
                }
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cli = Path(REAL_CLI).resolve()
    source = Path(os.environ["ZCODE_TEST_SOURCE"])
    vendor_home = tmp_path / "vendor"
    vendor_home.mkdir()
    builtin = vendor_home / "builtin.json"
    shutil.copyfile(source / "config/provider/zcode-builtin.json", builtin)
    personal = vendor_home / "personal.json"
    personal.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "config": {
                    "defaultModelSelection": {"providerId": "mock", "modelId": "mock-zcode"},
                    "providerConfigRules": {
                        "providerRules": [
                            {
                                "providerId": "mock",
                                "config": {
                                    "group": "standard-personal",
                                    "api": {
                                        "type": "openai-chat-completions",
                                        "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                                    },
                                    "access": {"type": "api-key", "apiKey": "test-only"},
                                    "personalModelIds": ["mock-zcode"],
                                    "modelOrder": ["mock-zcode"],
                                },
                            }
                        ]
                    },
                    "modelConfigRules": {
                        "providerModelRules": [],
                        "manualProviderModelRules": [
                            {
                                "providerId": "mock",
                                "modelId": "mock-zcode",
                                "config": {
                                    "enabled": True,
                                    "properties": {
                                        "contextWindow": 128000,
                                        "supportsJsonSchemaOutput": False,
                                        "supportsNativeWebSearch": False,
                                        "supportsMidConversationSystem": False,
                                        "inputFormat": {
                                            "supportsImage": True,
                                            "supportsVideo": False,
                                            "supportsPdf": False,
                                        },
                                    },
                                    "optionSpecs": {
                                        "reasoningLevel": {"values": ["high"], "map": "{}"},
                                        "maxOutputTokens": {"max": 4096},
                                    },
                                },
                            }
                        ],
                    },
                },
            }
        )
    )
    monkeypatch.setenv("ZCODE_DATA_BASE_DIR", str(vendor_home))
    monkeypatch.setenv("HOME", str(vendor_home))
    monkeypatch.setenv("USERPROFILE", str(vendor_home))
    monkeypatch.setenv("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE", str(personal))
    monkeypatch.setenv("ZCODE_BUILTIN_PROVIDER_CONFIG_FILE", str(builtin))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = ZCodeExecutor(zcode_path=str(cli), cwd=str(workspace))
    yield executor, requests, replies, received, workspace
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


async def collect(executor, content):
    return [
        event
        async for event in executor.run_turn(
            [{"role": "user", "content": content, "session_id": "real-session"}], [], ""
        )
    ]


async def test_real_stream_reasoning_usage_and_resume(real_zcode):
    executor, requests, replies, _, _ = real_zcode
    replies.extend([{"text": "copper lighthouse", "reasoning": "checking"}, {"text": "remembered"}])
    try:
        events = await collect(executor, "Remember copper lighthouse")
        session_id = executor._session_map["real-session"]
        followup = await collect(executor, "What did I ask you to remember?")
        assert executor._session_map["real-session"] == session_id
        assert any(isinstance(event, TextChunk) for event in events)
        assert any(isinstance(event, ReasoningChunk) for event in events)
        assert any(isinstance(event, TurnComplete) and event.usage for event in events)
        assert any(isinstance(event, TurnComplete) for event in followup)
        assert "copper lighthouse" in json.dumps(requests[-1]["messages"])
    finally:
        await executor.close()


@pytest.mark.parametrize(
    "tool,args,success",
    [
        ("Read", {"file_path": "hello.txt"}, True),
        ("Write", {"file_path": "created.txt", "content": "written by real ZCode"}, True),
        ("Read", {"file_path": "missing.txt"}, False),
    ],
)
async def test_real_tools(real_zcode, tool, args, success):
    executor, requests, replies, _, workspace = real_zcode
    (workspace / "hello.txt").write_text("read by real ZCode")
    replies.extend([{"tool": (tool, args)}, {"text": "done"}])
    try:
        events = await collect(executor, "Use your file tool")
        assert any(isinstance(event, ToolCallRequest) and event.name == tool for event in events)
        status = ToolCallStatus.SUCCESS if success else ToolCallStatus.ERROR
        assert any(
            isinstance(event, ToolCallComplete) and event.status == status for event in events
        )
        assert len(requests) == 2
        if tool == "Write":
            assert (workspace / "created.txt").read_text() == "written by real ZCode"
    finally:
        await executor.close()


async def test_real_file_and_image_attachments(real_zcode):
    executor, requests, replies, _, workspace = real_zcode
    image_path = workspace / "source.png"
    Image.new("RGB", (8, 8), "red").save(image_path)
    image = base64.b64encode(image_path.read_bytes()).decode()
    replies.extend([{"text": "attachment received"}, {"text": "image received"}])
    try:
        events = await collect(
            executor,
            [
                {"type": "input_text", "text": "Read this attachment"},
                {
                    "type": "input_file",
                    "filename": "note.txt",
                    "file_data": "data:text/plain;base64,"
                    + base64.b64encode(b"attachment marker").decode(),
                },
            ],
        )
        assert any(isinstance(event, TurnComplete) for event in events)
        key = executor._attachment_keys["real-session"]
        from omnigent.inner.native_attachments import attachment_cache_dir

        cache = attachment_cache_dir(key)
        assert not cache.resolve().is_relative_to(workspace)
        assert (cache / "note.txt").read_text() == "attachment marker"
        events = await collect(
            executor,
            [
                {"type": "input_text", "text": "Describe this image"},
                {
                    "type": "input_image",
                    "filename": "pixel.png",
                    "image_url": "data:image/png;base64," + image,
                },
            ],
        )
        assert any(isinstance(event, TurnComplete) for event in events)
        assert "image_url" in json.dumps(requests[-1]), json.dumps(requests[-1]["messages"])[-5000:]
        await executor.close_session("real-session")
        assert not cache.exists()
    finally:
        await executor.close()


@pytest.mark.parametrize("action", ["interrupt", "timeout"])
async def test_real_cancel_and_timeout(real_zcode, monkeypatch, action):
    from omnigent.community.harness.zcode import zcode_executor as module

    executor, _, replies, received, _ = real_zcode
    replies.append({"hang": True})
    if action == "timeout":
        monkeypatch.setattr(module, "_TURN_TIMEOUT_S", 15)
    task = asyncio.create_task(collect(executor, "Wait for a response"))
    try:
        assert await asyncio.to_thread(received.wait, 25)
        if action == "interrupt":
            assert await executor.interrupt_session("real-session")
        events = await asyncio.wait_for(task, 30)
        expected = TurnCancelled if action == "interrupt" else ExecutorError
        assert any(isinstance(event, expected) for event in events)
        assert executor._proc is None
    finally:
        await executor.close()
        if not task.done():
            task.cancel()


@pytest.mark.parametrize("mode", ["onDemand", "alwaysOn"])
async def test_real_workflow_modes_are_accepted(real_zcode, mode):
    executor, requests, _, _, _ = real_zcode
    executor._workflow_mode = mode
    try:
        events = await collect(executor, "Say pong")
        assert any(isinstance(event, TurnComplete) for event in events)
        if mode == "alwaysOn":
            assert any(
                tool["function"]["name"] == "CreateWorkflow" for tool in requests[0]["tools"]
            )
        else:
            assert "workflow" in json.dumps(requests[0]).lower()
    finally:
        await executor.close()


def test_real_cli_through_plugin_http_app(real_zcode, monkeypatch):
    from omnigent.community.harness.zcode.zcode_harness import create_app

    executor, _, _, _, workspace = real_zcode
    monkeypatch.setenv("OMNIGENT_ZCODE_PATH", executor._zcode_path)
    monkeypatch.setenv("HARNESS_ZCODE_CWD", str(workspace))
    app = create_app()
    app.state.conversation_id = "real-http"
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        for text in ["Remember a phrase", "Repeat the phrase"]:
            response = client.post(
                "/v1/sessions/real-http/events",
                json={
                    "type": "message",
                    "role": "user",
                    "model": "zcode",
                    "content": text,
                },
            )
            assert response.status_code == 200, response.text
            assert "response.completed" in response.text
            assert "pong" in response.text
