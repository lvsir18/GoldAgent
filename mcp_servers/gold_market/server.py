"""Gold Market MCP Server backed by shared domain services."""

try:
    from mcp.server import MCPServer as FastMCP  # MCP SDK 2.x
except ImportError:  # pragma: no cover - compatibility with MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP

from backend.app.core.container import build_container

mcp = FastMCP("Gold Market MCP")
services = build_container()


@mcp.tool()
async def get_gold_price(symbol: str = "AU0", market: str = "CN", period: str = "3y") -> dict:
    """Get latest gold price with source and freshness metadata."""
    return (await services.market.summary(symbol, market, period)).model_dump(mode="json")


@mcp.tool()
async def get_gold_history(symbol: str = "AU0", market: str = "CN", period: str = "3y", limit: int = 120) -> dict:
    """Get bounded gold OHLCV history."""
    return (await services.market.history(symbol, market, period, limit)).model_dump(mode="json")


@mcp.tool()
async def calculate_indicators(symbol: str = "AU0", market: str = "CN", period: str = "3y") -> dict:
    """Calculate the latest technical snapshot."""
    source = await services.market.history_frame(symbol, market, period)
    _, snapshot = services.technical.calculate(source.frame, source.metadata)
    return snapshot.model_dump(mode="json")


@mcp.tool()
async def get_exchange_rate(pair: str = "USD/CNY") -> dict:
    """Get a direct exchange rate or an explicit availability error."""
    try:
        value, metadata = await services.market.provider.get_exchange_rate(pair)
    except NotImplementedError:
        return {"success": False, "error": {"code": "FX_PROVIDER_UNAVAILABLE", "message": "Direct FX provider is not configured"}}
    return {"success": True, "rate": value, "metadata": metadata.model_dump(mode="json")}


if __name__ == "__main__":
    mcp.run()
