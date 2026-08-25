export type SourceMetadata = { source: string; source_type: "direct" | "derived" | "cache" | "simulation"; is_derived: boolean; is_cached: boolean; is_stale: boolean; retrieved_at: string; data_start?: string; data_end?: string; currency: string; market: string; symbol: string; reference?: string };
export type MarketPoint = { timestamp: string; open: number; high: number; low: number; close: number; volume: number; is_provisional?: boolean };
export type MarketSummary = {
  price: number;
  previous_close?: number;
  previous_settlement?: number;
  trading_date?: string;
  quote_time?: string;
  is_realtime: boolean;
  change_basis: "previous_close" | "previous_settlement";
  change_1d_pct?: number;
  change_1w_pct?: number;
  change_1m_pct?: number;
  usd_cny?: number;
  metadata: SourceMetadata;
};
export type TechnicalSnapshot = { timestamp: string; close: number; ma: Record<string, number | null>; rsi?: number; macd?: number; atr?: number; volatility?: number; trend: string; support?: number; resistance?: number; metadata: SourceMetadata };
export type Session = { id: string; title: string; status: string; created_at: string; updated_at: string };
export type ApiEnvelope<T> = { success: boolean; data: T; meta: Record<string, unknown>; error?: { code: string; message: string } };
