# Gold Market MCP Server

Run with `python -m mcp_servers.gold_market.server`. It exposes price, bounded history,
technical indicators, and an explicit FX availability result. Business logic remains in
GoldAgent services; this package only adapts schemas and MCP transport.
