import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownContent } from "@/components/common/markdown-content";

describe("MarkdownContent", () => {
  it("renders headings, emphasis, lists, tables, and safe links", () => {
    render(<MarkdownContent content={`## 当前黄金市场情况

**实时价格**：944.58元/克

- 日内波动：943.20 - 955.52元
- 短期趋势：承压

| 字段 | 数值 |
| --- | --- |
| RSI | 55 |

[来源](https://example.com)`} />);

    expect(screen.getByRole("heading", { name: "当前黄金市场情况" })).toBeInTheDocument();
    expect(screen.getByText("实时价格").tagName).toBe("STRONG");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "来源" })).toHaveAttribute("target", "_blank");
  });
});
