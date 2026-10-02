"""Stdio MCP bridge for Echo's Hoard.

It never opens the database: every tool call is proxied to the running app (`POST /api/agent/call`) with the Bearer token
from `<DATA_DIR>/mcp-token`. The tool list comes from `GET /api/agent/tools` (refreshed while the bridge runs), so the
bridge and the app can never disagree. When nothing answers, the bridge starts the app itself (`python -m echo`, detached,
on the port of ECHO_URL) and waits for it; ECHO_BRIDGE_AUTOSTART=0 turns that off. The bridge is the shared
`hoard_link.bridge.CatalogBridge`.
"""

from __future__ import annotations

import sys

from echo.hoard_link.bridge import CatalogBridge


def build() -> CatalogBridge:
    return CatalogBridge(app="echo", service="echo-hoard", package="echo", default_port=5188, data_dir_env="ECHO_DATA_DIR",
                         title="Echo's Hoard", root=__file__)


if __name__ == "__main__":
    sys.exit(build().run_bridge())
