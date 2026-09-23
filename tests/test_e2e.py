"""Boot the real app in a subprocess (fake clipboard backend), then talk to it
over HTTP and through the MCP stdio bridge."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from echo.port import free_port

ROOT = Path(__file__).resolve().parent.parent


def wait_health(url: str, process: subprocess.Popen, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"app exited early with code {process.returncode}")
        try:
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise AssertionError("app did not become healthy")


@pytest.fixture
def app_process(tmp_path):
    port = free_port()
    data_dir = tmp_path / "data"
    env = {
        **os.environ,
        "ECHO_DATA_DIR": str(data_dir),
        "ECHO_PORT": str(port),
        "PORT_STRICT": "1",
        "ECHO_BACKEND": "fake",
        "PYTHONUNBUFFERED": "1",
    }
    process = subprocess.Popen([sys.executable, "-m", "echo"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_health(url, process)
        yield url, data_dir, env
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()


def test_subprocess_http_and_mcp_bridge(app_process):
    url, data_dir, env = app_process
    health = httpx.get(f"{url}/api/health").json()
    assert health["service"] == "echo-hoard" and health["dataDirConfigured"] is True
    tools = httpx.get(f"{url}/api/agent/tools").json()["tools"]
    assert [t["name"] for t in tools][:2] == ["clip_recent", "clip_search"]

    token = (data_dir / "mcp-token").read_text().strip()
    assert len(token) == 64
    assert httpx.post(f"{url}/api/agent/call", json={"name": "clip_status"}).status_code == 401
    auth = {"Authorization": f"Bearer {token}"}

    status = httpx.post(f"{url}/api/agent/call", json={"name": "clip_status"}, headers=auth).json()
    assert status["backend"] == "fake"

    set_result = httpx.post(
        f"{url}/api/agent/call", json={"name": "clip_set", "arguments": {"text": "Copiado end-to-end"}}, headers=auth
    ).json()
    assert set_result["ok"] is True
    clip_id = set_result["clip"]["id"]

    recent = httpx.post(f"{url}/api/agent/call", json={"name": "clip_recent", "arguments": {"n": 5}}, headers=auth).json()
    assert any(c["id"] == clip_id for c in recent["clips"])

    async def through_mcp():
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "mcp_server.py")],
            env={**env, "ECHO_URL": url, "ECHO_TOKEN_FILE": str(data_dir / "mcp-token")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                assert "sensitive" in (init.instructions or "").lower() or "clipboard" in (init.instructions or "").lower()
                listed = await session.list_tools()
                names = [t.name for t in listed.tools]
                assert names == [t["name"] for t in tools]
                write_tool = next(t for t in listed.tools if t.name == "clip_set")
                assert write_tool.annotations.readOnlyHint is False
                destructive_tool = next(t for t in listed.tools if t.name == "clip_delete")
                assert destructive_tool.annotations.destructiveHint is True

                recent_via_mcp = json.loads((await session.call_tool("clip_recent", {"n": 5})).content[0].text)
                assert any(c["id"] == clip_id for c in recent_via_mcp["clips"])

                got = json.loads((await session.call_tool("clip_get", {"id": clip_id})).content[0].text)
                assert got["text"] == "Copiado end-to-end"

                bad = json.loads((await session.call_tool("clip_get", {"id": 999999})).content[0].text)
                assert "error" in bad

    asyncio.run(through_mcp())
