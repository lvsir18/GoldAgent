"use client";
import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { forecastApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { ResultChart } from "@/components/charts/result-chart";
import { SourceBadge } from "@/components/common/source-badge";
import { useLanguage } from "@/i18n/language";

export default function ForecastPage() {
  const { text } = useLanguage();
  const qc = useQueryClient();
  const [horizon,setHorizon] = useState(5), [model,setModel] = useState("exponential"), [id,setId] = useState("");
  const history = useQuery({ queryKey: ["forecasts"], queryFn: forecastApi.list });
  useEffect(() => { if (!id && history.data?.length) setId(history.data[0].id); }, [history.data, id]);
  const result = useQuery({ queryKey: ["forecast",id], queryFn: () => forecastApi.get(id), enabled: Boolean(id) });
  const m = useMutation({ mutationFn: () => forecastApi.create({symbol:"AU0",horizon,model}), onSuccess: data => { qc.setQueryData(["forecast",data.id],data); setId(data.id); qc.invalidateQueries({queryKey:["forecasts"]}); } });
  const submit = (e:FormEvent) => { e.preventDefault(); m.mutate(); };
  const data = result.data;
  const modelName: Record<string,string> = { exponential: text("指数平滑", "Exponential"), linear: text("线性趋势", "Linear"), ma: text("移动平均", "Moving average") };
  return <div className="space-y-4"><PageHeading eyebrow="MODEL ESTIMATE" title={text("黄金价格预测", "Gold Price Forecast")} description={text("同周期滚动评估，对比价格不变基准。历史表现不代表未来准确率。", "Walk-forward evaluation at the selected horizon against a last-price baseline. Historical performance is not a future probability.")}/>
    <form onSubmit={submit} className="card grid gap-4 p-5 sm:grid-cols-3"><label className="text-sm">{text("预测周期（日线步数）", "Horizon (daily observations)")}<input type="number" min={1} max={30} value={horizon} onChange={e=>setHorizon(Number(e.target.value))} className="mt-2 w-full rounded border border-line bg-canvas p-2"/></label><label className="text-sm">{text("模型", "Model")}<select value={model} onChange={e=>setModel(e.target.value)} className="mt-2 w-full rounded border border-line bg-canvas p-2">{Object.entries(modelName).map(([v,label]) => <option key={v} value={v}>{label}</option>)}</select></label><button disabled={m.isPending} className="mt-6 rounded bg-gold p-2 font-medium text-black disabled:opacity-50">{m.isPending ? text("计算中…", "Calculating…") : text("运行预测", "Run forecast")}</button></form>
    <label className="block text-sm">{text("历史预测", "Forecast history")}<select value={id} onChange={e => setId(e.target.value)} className="ml-3 max-w-full rounded border border-line bg-surface p-2"><option value="">{text("选择记录", "Select a record")}</option>{history.data?.map(r => <option value={r.id} key={r.id}>{new Date(r.created_at).toLocaleString()} · {modelName[r.request.model]} · T+{r.request.horizon}</option>)}</select></label>
    {(m.error || result.error || history.error) && <p role="alert" className="text-negative">{m.error?.message || result.error?.message || history.error?.message}</p>}
    {data && <><section className="card p-5"><SourceBadge source={data.metadata}/><p className="my-3 text-xs text-muted">{text("本次结果", "Selected result")} · {modelName[data.request.model]} · T+{data.request.horizon} · {text("滚动样本", "Evaluation samples")} {data.metrics.sample_count ?? "—"} · {text("最小训练窗口", "Minimum training size")} {data.metrics.min_train ?? "—"}</p><div className="grid gap-3 sm:grid-cols-4"><Metric label={text("参考价格（元/克）", "Reference price (CNY/g)")} value={data.current_price.toFixed(2)}/><Metric label={text("平均绝对误差 MAE（元/克）", "MAE (CNY/g)")} value={data.metrics.mae?.toFixed(2)??"—"}/><Metric label={text("价格不变基准 MAE", "Last-price baseline MAE")} value={data.metrics.baseline_mae?.toFixed(2)??"—"}/><Metric label={text("历史方向命中率", "Historical directional accuracy")} value={data.metrics.direction_accuracy==null?"—":`${(data.metrics.direction_accuracy*100).toFixed(1)}%`}/></div><p className="mt-3 text-xs text-muted">{text("评估目标日期范围", "Evaluation target dates")}：{data.metrics.evaluation_start ?? "—"} → {data.metrics.evaluation_end ?? "—"}</p><p className="mt-4 text-sm text-warning">{text("模型估计不保证未来价格；仅用已完成日线，不是统计置信区间。", "Model estimates are not guaranteed prices or calibrated confidence intervals; only completed daily observations are used.")}</p></section>
    <ResultChart title={text("预测路径与价格不变基准", "Forecast path vs last-price baseline")} labels={["T", ...data.predicted_prices.map((_:number,i:number)=>`T+${i+1}`)]} unit="CNY/g" series={[{name:text("模型预测", "Forecast"),color:"#d6aa4b",values:[data.current_price,...data.predicted_prices]},{name:text("价格不变基准", "Last-price baseline"),color:"#a8a79f",values:Array(data.predicted_prices.length+1).fill(data.current_price)}]}/></>}
  </div>;
}
function Metric({label,value}:{label:string;value:string}){return <div className="rounded-lg bg-canvas p-3"><div className="text-xs text-muted">{label}</div><div className="tabular mt-1 text-lg">{value}</div></div>}
