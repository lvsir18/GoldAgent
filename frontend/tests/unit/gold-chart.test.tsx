import { describe, expect, it } from "vitest";

import { toBusinessDay } from "@/components/charts/gold-chart";

describe("gold chart trading dates", () => {
  it("keeps a daily candle on its source trading date without timezone conversion", () => {
    expect(toBusinessDay("2026-08-21T00:00:00")).toEqual({ year: 2026, month: 8, day: 21 });
    expect(toBusinessDay("2026-08-24T00:00:00Z")).toEqual({ year: 2026, month: 8, day: 24 });
  });
});
