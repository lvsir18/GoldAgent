import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ErrorState, LoadingState } from "@/components/common/async-state";
import { LanguageProvider } from "@/i18n/language";

function LanguageTestProvider({ children }: { children: React.ReactNode }) {
  return <LanguageProvider>{children}</LanguageProvider>;
}

describe("async state components", () => {
  it("renders loading and empty states", () => {
    const { rerender } = render(<LoadingState label="加载行情" />, { wrapper: LanguageTestProvider });
    expect(screen.getByText("加载行情…")).toBeInTheDocument();
    rerender(<EmptyState title="暂无报告" detail="先生成一份" />);
    expect(screen.getByText("暂无报告")).toBeInTheDocument();
    expect(screen.getByText("先生成一份")).toBeInTheDocument();
  });

  it("supports retry from an error state", () => {
    const retry = vi.fn();
    render(<ErrorState message="offline" retry={retry} />, { wrapper: LanguageTestProvider });
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
