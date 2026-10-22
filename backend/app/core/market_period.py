"""Daily-history lookback syntax shared by API, tools and calculations."""
import re
from typing import Annotated
from pydantic import BeforeValidator


def normalize_period(value: str) -> str:
    period = str(value).strip().lower()
    if period in {"all", "max"}:
        return "all"
    match = re.fullmatch(r"([1-9]\d*)(mo|m|w|d|y)", period)
    if not match:
        raise ValueError("Use a daily-history lookback such as 30d, 2w, 1mo, 3y or all")
    amount, unit = int(match[1]), match[2]
    unit = "mo" if unit == "m" else unit
    if amount > {"d":36525, "w":5200, "mo":1200, "y":100}[unit]:
        raise ValueError("History lookback cannot exceed 100 years")
    return f"{amount}{unit}"


MarketPeriod = Annotated[str, BeforeValidator(normalize_period)]
