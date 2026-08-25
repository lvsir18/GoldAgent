"use client";

import { createChart, CandlestickSeries, type BusinessDay } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { MarketPoint } from "@/types/api";

export function toBusinessDay(timestamp: string): BusinessDay {
  const [year, month, day] = timestamp.slice(0, 10).split("-").map(Number);
  return { year, month, day };
}

export function GoldChart({ points }: { points: MarketPoint[] }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, { height: 360, layout: { background: { color: "#191a17" }, textColor: "#a8a79f" }, grid: { vertLines: { color: "#292a24" }, horzLines: { color: "#292a24" } }, rightPriceScale: { borderColor: "#303129" }, timeScale: { borderColor: "#303129", timeVisible: false } });
    const series = chart.addSeries(CandlestickSeries, { upColor: "#69a67a", downColor: "#c66f6f", borderVisible: false, wickUpColor: "#69a67a", wickDownColor: "#c66f6f" });
    series.setData(points.map(point => {
      const provisionalColor = point.is_provisional ? "#d6aa4b" : undefined;
      return {
        time: toBusinessDay(point.timestamp),
        open: point.open, high: point.high, low: point.low, close: point.close,
        ...(provisionalColor ? { color: provisionalColor, borderColor: provisionalColor, wickColor: provisionalColor } : {}),
      };
    }));
    if (points.length > 120) chart.timeScale().setVisibleLogicalRange({ from: points.length - 120, to: points.length + 2 });
    else chart.timeScale().fitContent();
    const resize = () => chart.applyOptions({ width: container.current?.clientWidth ?? 600 });
    resize();
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.remove(); };
  }, [points]);
  return <div ref={container} className="w-full" aria-label="黄金 K 线图"/>;
}
