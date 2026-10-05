"use client";
import { Advisory, Badge, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

const show = (v: any): string => (v == null ? "-" : typeof v === "object" ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(", ") : String(v));

export default function ModelCards() {
  const { tick } = useSession();
  const { data, error, loading } = useLoad(() => api("/models/cards"), [tick]);
  return (
    <div>
      <PageTitle title="Model Cards" question="What does each model do, how accurate is it, and what are its limits?" />
      <div className="mb-4"><Advisory /></div>
      {error && <ErrorBox>{error}</ErrorBox>}
      {loading && !data ? <Loading /> : !data?.cards?.length ? <Card><Empty>{data?.message || "No model cards found."}</Empty></Card> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.cards.map((c: any) => (
            <Card key={c.name}>
              <CardHeader title={c.name} sub={`Version ${c.version}${c.trained_on ? ` · trained ${c.trained_on}` : ""}`} right={<Badge tone="blue">Advisory only</Badge>} />
              <dl className="space-y-2 p-4 text-sm">
                <div><dt className="text-xs font-medium text-slate-500">What it does</dt><dd>{c.purpose}</dd></div>
                <div><dt className="text-xs font-medium text-slate-500">Training data</dt><dd>{c.data}</dd></div>
                <div><dt className="text-xs font-medium text-slate-500">Accuracy</dt>
                  <dd><ul className="text-sm">{Object.entries(c.metrics || {}).map(([k, v]) => <li key={k} className="flex justify-between gap-3"><span className="text-slate-600">{k}</span><span className="text-right font-medium">{show(v)}</span></li>)}</ul></dd></div>
                {c.false_alarm && <div><dt className="text-xs font-medium text-slate-500">False-alarm rate (alerts an Engineering Officer marked “False alarm”)</dt>
                  <dd>{c.false_alarm.rate == null ? "No reviewed alerts yet" : `${(c.false_alarm.rate * 100).toFixed(0)}% (${c.false_alarm.false_alarms} of ${c.false_alarm.reviewed} reviewed alerts)`}</dd></div>}
                <div><dt className="text-xs font-medium text-slate-500">Limits</dt><dd className="rounded bg-amber-50 p-2 text-amber-900">{c.limits}</dd></div>
                <div><dt className="text-xs font-medium text-slate-500">Approved by</dt><dd>{c.approved_by || "Not approved for use"}</dd></div>
              </dl>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
