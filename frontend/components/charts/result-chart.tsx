"use client";
import { useLanguage } from "@/i18n/language";

type Series = { name: string; color: string; values: number[] };
/** Bounded SVG chart: data only, no model-generated executable UI. */
export function ResultChart({ title, labels, series, unit = "" }: { title: string; labels: string[]; series: Series[]; unit?: string }) {
  const { text } = useLanguage();
  const finite = series.flatMap(s => s.values).filter(Number.isFinite);
  if (!finite.length) return null;
  const min = Math.min(...finite), max = Math.max(...finite);
  const padding = Math.max((max - min) * 0.08, Math.abs(max) * 0.001, 0.01);
  const lower = min - padding, upper = max + padding;
  const y = (v: number) => 190 - (v - lower) / (upper - lower) * 170;
  const x = (i: number, length: number) => 65 + i / Math.max(length - 1, 1) * 700;
  return <figure className="card min-w-0 p-4"><figcaption className="mb-2 font-medium">{title}</figcaption><svg viewBox="0 0 800 225" role="img" aria-label={title} className="w-full"><title>{title}</title>{[0,1,2,3].map(i => { const v = lower + (upper - lower) * i / 3; return <g key={i}><line x1="65" x2="765" y1={y(v)} y2={y(v)} stroke="#303129"/><text x="58" y={y(v) + 4} fill="#a8a79f" fontSize="11" textAnchor="end">{v.toFixed(2)}</text></g>; })}{series.map(s => <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="2.5" points={s.values.map((v,i) => `${x(i,s.values.length)},${y(v)}`).join(" ")}><title>{s.name} · {s.values.at(-1)?.toFixed(2)} {unit}</title></polyline>)}<text x="65" y="217" fill="#a8a79f" fontSize="11">{labels[0]}</text><text x="765" y="217" textAnchor="end" fill="#a8a79f" fontSize="11">{labels.at(-1)}</text></svg><div className="flex flex-wrap gap-4 text-xs">{series.map(s => <span key={s.name} style={{ color: s.color }}>{s.name} · {text("末值", "Last")} {s.values.at(-1)?.toFixed(2)} {unit}</span>)}</div></figure>;
}
