"""GoldAgent API entry point.

The 1.x rule router and JSON-backed CLI were removed after the Phase 14
production gates passed. Domain operations are available through the FastAPI
API, Next.js workbench, and MCP server.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the GoldAgent API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--reload", action="store_true", help="Enable development auto-reload")
    args = parser.parse_args()
    uvicorn.run("backend.app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
