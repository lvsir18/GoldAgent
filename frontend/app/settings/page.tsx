"use client";

import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";
import { userApi } from "@/services/api/domain";

type Preferences = {
  response_language: "auto" | "zh" | "en";
  response_style: "concise" | "balanced" | "detailed";
  tone: "professional" | "friendly" | "direct";
  show_sources: boolean;
  custom_instructions: string;
};

type RiskProfile = {
  risk_level: "conservative" | "balanced" | "aggressive";
  horizon: "short" | "medium" | "long";
  max_drawdown_pct: string;
  notes: string;
};

const defaultPreferences: Preferences = {
  response_language: "auto",
  response_style: "balanced",
  tone: "professional",
  show_sources: true,
  custom_instructions: "",
};

const defaultRisk: RiskProfile = {
  risk_level: "balanced",
  horizon: "medium",
  max_drawdown_pct: "",
  notes: "",
};

const control = "focus-ring mt-2 w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm";

export default function SettingsPage() {
  const { text } = useLanguage();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: userApi.me });
  const [displayName, setDisplayName] = useState("");
  const [preferences, setPreferences] = useState<Preferences>(defaultPreferences);
  const [risk, setRisk] = useState<RiskProfile>(defaultRisk);

  useEffect(() => {
    if (!me.data) return;
    setDisplayName(me.data.profile?.display_name ?? "");
    setPreferences({ ...defaultPreferences, ...(me.data.profile?.preferences ?? {}) });
    setRisk({
      ...defaultRisk,
      ...(me.data.risk_profile ?? {}),
      max_drawdown_pct: me.data.risk_profile?.max_drawdown_pct?.toString() ?? "",
    });
  }, [me.data]);

  const save = useMutation({
    mutationFn: async () => Promise.all([
      userApi.updateProfile({ display_name: displayName || null, preferences }),
      userApi.updateRisk({
        risk_level: risk.risk_level,
        horizon: risk.horizon,
        max_drawdown_pct: risk.max_drawdown_pct === "" ? null : Number(risk.max_drawdown_pct),
        notes: risk.notes,
      }),
    ]),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return (
    <div>
      <PageHeading
        eyebrow="PERSONALIZATION"
        title={text("个性化设置", "Personalization")}
        description={text(
          "控制 Agent 的回答语言、详细程度、语气和风险表达。保存后会从下一次对话开始生效。",
          "Control the Agent's language, level of detail, tone, and risk framing. Changes apply to your next conversation.",
        )}
      />

      {me.isLoading && <p className="text-sm text-muted">{text("正在加载设置…", "Loading settings…")}</p>}
      {me.isError && <p className="text-sm text-negative">{me.error.message}</p>}

      {me.data && (
        <form onSubmit={submit} className="space-y-4">
          <section className="card p-5">
            <h2 className="font-medium">{text("回答偏好", "Response preferences")}</h2>
            <p className="mt-1 text-sm text-muted">{text("这些选项只改变表达方式，不会绕过数据核验、工具调用或金融安全规则。", "These options affect presentation only and cannot override data verification, tool use, or financial safety rules.")}</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="text-sm">{text("希望 Agent 如何称呼你", "What should the Agent call you?")}
                <input value={displayName} maxLength={100} onChange={event => setDisplayName(event.target.value)} placeholder={text("例如：小李", "For example: Alex")} className={control} />
              </label>
              <label className="text-sm">{text("回答语言", "Response language")}
                <select value={preferences.response_language} onChange={event => setPreferences({ ...preferences, response_language: event.target.value as Preferences["response_language"] })} className={control}>
                  <option value="auto">{text("跟随提问语言", "Match the question")}</option>
                  <option value="zh">{text("中文", "Chinese")}</option>
                  <option value="en">{text("英文", "English")}</option>
                </select>
              </label>
              <label className="text-sm">{text("回答详细程度", "Level of detail")}
                <select value={preferences.response_style} onChange={event => setPreferences({ ...preferences, response_style: event.target.value as Preferences["response_style"] })} className={control}>
                  <option value="concise">{text("简洁", "Concise")}</option>
                  <option value="balanced">{text("平衡", "Balanced")}</option>
                  <option value="detailed">{text("详细", "Detailed")}</option>
                </select>
              </label>
              <label className="text-sm">{text("表达语气", "Tone")}
                <select value={preferences.tone} onChange={event => setPreferences({ ...preferences, tone: event.target.value as Preferences["tone"] })} className={control}>
                  <option value="professional">{text("专业克制", "Professional")}</option>
                  <option value="friendly">{text("友好易懂", "Friendly")}</option>
                  <option value="direct">{text("直接明确", "Direct")}</option>
                </select>
              </label>
            </div>
            <label className="mt-4 block text-sm">{text("自定义要求", "Custom instructions")}
              <textarea value={preferences.custom_instructions} maxLength={2000} rows={4} onChange={event => setPreferences({ ...preferences, custom_instructions: event.target.value })} placeholder={text("例如：先给结论，再解释指标；专业术语附简短说明。", "For example: Lead with the conclusion and briefly explain technical terms.")} className={control} />
            </label>
            <label className="mt-4 flex items-center gap-2 text-sm">
              <input type="checkbox" checked={preferences.show_sources} onChange={event => setPreferences({ ...preferences, show_sources: event.target.checked })} className="h-4 w-4 accent-gold" />
              {text("回答引用实时行情、新闻或知识库时展示来源", "Show sources when answers use live prices, news, or knowledge documents")}
            </label>
          </section>

          <section className="card p-5">
            <h2 className="font-medium">{text("投资与风险偏好", "Investment and risk preferences")}</h2>
            <p className="mt-1 text-sm text-muted">{text("Agent 会结合这些设置和投资组合模块中已保存的持仓进行分析。", "The Agent combines these preferences with holdings saved in the Portfolio module.")}</p>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <label className="text-sm">{text("风险承受能力", "Risk tolerance")}
                <select value={risk.risk_level} onChange={event => setRisk({ ...risk, risk_level: event.target.value as RiskProfile["risk_level"] })} className={control}>
                  <option value="conservative">{text("稳健", "Conservative")}</option>
                  <option value="balanced">{text("均衡", "Balanced")}</option>
                  <option value="aggressive">{text("进取", "Aggressive")}</option>
                </select>
              </label>
              <label className="text-sm">{text("投资周期", "Investment horizon")}
                <select value={risk.horizon} onChange={event => setRisk({ ...risk, horizon: event.target.value as RiskProfile["horizon"] })} className={control}>
                  <option value="short">{text("短期（1 年内）", "Short term")}</option>
                  <option value="medium">{text("中期（1–3 年）", "Medium term")}</option>
                  <option value="long">{text("长期（3 年以上）", "Long term")}</option>
                </select>
              </label>
              <label className="text-sm">{text("可接受最大回撤（%）", "Maximum acceptable drawdown (%)")}
                <input type="number" min={0} max={100} step={0.1} value={risk.max_drawdown_pct} onChange={event => setRisk({ ...risk, max_drawdown_pct: event.target.value })} className={control} />
              </label>
            </div>
            <label className="mt-4 block text-sm">{text("风险偏好补充", "Risk notes")}
              <textarea value={risk.notes} maxLength={2000} rows={3} onChange={event => setRisk({ ...risk, notes: event.target.value })} placeholder={text("例如：更关注回撤，不接受高频交易。", "For example: Prioritize drawdown control and avoid high-frequency trading.")} className={control} />
            </label>
          </section>

          <div className="flex items-center gap-3">
            <button disabled={save.isPending} className="focus-ring rounded-lg bg-gold px-5 py-2.5 text-sm font-medium text-black disabled:opacity-40">
              {save.isPending ? text("正在保存…", "Saving…") : text("保存个性化设置", "Save personalization")}
            </button>
            {save.isSuccess && <span className="text-sm text-positive">{text("已保存，将在下一次 Agent 对话中生效。", "Saved. Changes apply to your next Agent conversation.")}</span>}
            {save.isError && <span className="text-sm text-negative">{save.error.message}</span>}
          </div>
        </form>
      )}
    </div>
  );
}
