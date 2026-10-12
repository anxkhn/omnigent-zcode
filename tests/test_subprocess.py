"""Exercise the registered harness through its real HTTP subprocess."""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from omnigent.harness_plugins import harness_modules
from test_zcode import _write_fake_zcode


def test_harness_subprocess_streams_and_resumes(tmp_path):
    binary = tmp_path / "zcode"
    log = tmp_path / "argv.jsonl"
    socket = Path("/tmp") / f"oz-{uuid.uuid4().hex[:12]}.sock"
    _write_fake_zcode(binary)
    env = {
        **os.environ,
        "OMNIGENT_ZCODE_PATH": str(binary),
        "HARNESS_ZCODE_CWD": str(tmp_path),
        "ZCODE_TEST_LOG": str(log),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "omnigent.runtime.harnesses._runner",
            "--harness",
            "zcode",
            "--module",
            harness_modules()["zcode"],
            "--socket",
            str(socket),
            "--conversation-id",
            "plugin-smoke",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with httpx.Client(
            transport=httpx.HTTPTransport(uds=str(socket)),
            base_url="http://localhost",
            timeout=20,
        ) as client:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert process.poll() is None, process.stderr.read()
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("Harness subprocess did not become ready")
            for prompt in ("scenario:tools", "again"):
                response = client.post(
                    "/v1/sessions/plugin-smoke/events",
                    json={"type": "message", "role": "user", "model": "zcode", "content": prompt},
                )
                assert response.status_code == 200, response.text
                events = [
                    json.loads(line.removeprefix("data: "))
                    for line in response.text.splitlines()
                    if line.startswith("data: ")
                ]
                assert any(event["type"] == "response.output_text.delta" for event in events)
                assert events[-1]["type"] == "response.completed", events
                assert "pong" in response.text
            calls = [json.loads(line)["argv"] for line in log.read_text().splitlines()]
            assert "--resume" not in calls[0]
            assert calls[1][calls[1].index("--resume") + 1] == "sess-1"
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
        socket.unlink(missing_ok=True)
