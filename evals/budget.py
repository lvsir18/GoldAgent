"""Hard opt-in live-call budgets; no pricing assumptions and no hidden retries."""
import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from backend.app.llm.gateway import OpenAICompatibleGateway


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    max_calls: int = 64
    max_output_tokens: int = 65536
    max_input_chars: int = 750000
    wall_seconds: int = 900
    calls: int = 0
    output_reserved: int = 0
    input_chars: int = 0
    started: float = 0

    def __post_init__(self):
        self.started = time.monotonic()

    def reserve(self, tokens, chars):
        if (self.calls + 1 > self.max_calls or self.output_reserved + tokens > self.max_output_tokens
            or self.input_chars + chars > self.max_input_chars or time.monotonic() - self.started >= self.wall_seconds):
            raise BudgetExceeded("Evaluation budget exhausted")
        # Called without an await, so simultaneous asyncio tasks cannot oversubscribe.
        self.calls += 1
        self.output_reserved += tokens
        self.input_chars += chars

    def snapshot(self):
        return {name:getattr(self,name) for name in ("max_calls","max_output_tokens","max_input_chars","wall_seconds","calls","output_reserved","input_chars")}


class MeteredGateway:
    def __init__(self, inner, budget, ledger=None):
        self.inner, self.budget = inner, budget
        self.ledger = ledger if ledger is not None else {"calls":0,"prompt_tokens":0,"completion_tokens":0,"usage_complete":True}

    @asynccontextmanager
    async def session(self):
        async with self.inner.session():
            yield self

    def for_phase(self, phase):
        return MeteredGateway(self.inner.for_phase(phase), self.budget, self.ledger)

    async def chat(self, messages, tools=None):
        chars = len(json.dumps(self.inner._payload(messages, tools), ensure_ascii=False))
        self.budget.reserve(self.inner.max_tokens, chars)
        self.ledger["calls"] += 1
        # Disable Tenacity retry for the benchmark: every paid HTTP attempt must
        # reserve budget, and a timeout must not silently start another request.
        try:
            response = await OpenAICompatibleGateway.chat.__wrapped__(self.inner, messages, tools)
        except BaseException:
            self.ledger["usage_complete"] = False
            raise
        for key in ("prompt_tokens","completion_tokens"):
            value = getattr(response,key)
            if value is None:
                self.ledger["usage_complete"] = False
            else:
                self.ledger[key] += value
        return response
