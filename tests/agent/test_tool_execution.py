import asyncio
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from backend.app.agent.graph import GoldAgentRuntime
from backend.app.tools.registry import ToolRegistry, _bounded
from src.settings import AppSettings


class Args(BaseModel):
    value: int = 1


async def test_readonly_tools_are_bounded_parallel_and_keep_call_order():
    active = peak = 0
    async def slow(value=1):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return {"value":value}
    names = ["get_gold_spot_price", "get_market_history", "calculate_technical_indicators", "search_financial_news"]
    tools = [StructuredTool.from_function(coroutine=slow,name=n,description="offline readonly fixture",args_schema=Args) for n in names]
    runtime = GoldAgentRuntime(AppSettings(), None, ToolRegistry(tools))
    calls = [{"name": n, "args": {"value":i}, "id":str(i), "type":"tool_call"} for i,n in enumerate(names)]
    result = await runtime._execute_tools({"messages":[AIMessage(content="",tool_calls=calls)],"tool_results":[]})
    assert peak == 3
    assert [r["tool"] for r in result["tool_results"]] == names
    assert [r.tool_call_id for r in result["messages"][1:]] == ["0","1","2","3"]


async def test_identical_tool_arguments_share_one_provider_request_per_registry():
    count = 0
    async def provider(value):
        nonlocal count
        count += 1
        await asyncio.sleep(0)
        return {"value":value}
    tool = _bounded(provider, 2)
    assert await asyncio.gather(*(tool(value=1) for _ in range(4))) == [{"value":1}] * 4
    assert count == 1
    await tool(value=2)
    assert count == 2
