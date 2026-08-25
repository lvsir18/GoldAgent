"use client";
import { useQuery } from "@tanstack/react-query";
import { userApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";
export default function SettingsPage(){const { text }=useLanguage();const q=useQuery({queryKey:["me"],queryFn:userApi.me});return <div><PageHeading eyebrow="CONFIGURATION" title={text("设置", "Settings")} description={text("API Key 永远不会从后端返回到浏览器。模型和数据源由部署环境控制。", "API keys are never returned to the browser. Models and data sources are controlled by the deployment environment.")}/><section className="card p-5"><h2 className="font-medium">{text("当前身份", "Current identity")}</h2><pre className="mt-3 overflow-auto rounded bg-canvas p-4 text-sm text-muted">{q.data?JSON.stringify(q.data,null,2):text("加载中…", "Loading…")}</pre></section><section className="card mt-4 p-5"><h2 className="font-medium">{text("运行模式", "Runtime mode")}</h2><p className="mt-2 text-sm text-muted">Demo mode · MiMo provider · Streaming enabled · Agent max steps controlled by backend</p></section></div>}
