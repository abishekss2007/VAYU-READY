"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ForecastChart } from "@/components/forecast-chart";
import { ReviewDialog } from "@/components/review-dialog";
import { Advisory, Badge, Button, Card, CardHeader, cn, Empty, ErrorBox, healthBg, Loading, PageTitle, severityTone, Stat, useLoad } from "@/components/ui";
import { api, download } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

export default function Dashboard() {
  const { me, tick } = useSession();
  const router = useRouter();
  const [sq, setSq] = useState("");
  const { data: d, error, loading, reload } = useLoad(() => api(`/dashboard${sq ? `?squadron=${sq}` : ""}`), [tick, sq]);
  const [review, setReview] = useState<any>(null);
  const { busy, run } = useAction();

  if (loading && !d) return <Loading label="Loading readiness..." />;
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!d) return null;
  const k = d.kpis;
  const scoreTone = d.score >= 80 ? "text-ok" : d.score >= 60 ? "text-warn" : "text-crit";
  const q = sq ? `?squadron=${sq}` : "";

  return (
    <div>
      <PageTitle title={`Readiness Dashboard · ${d.squadron_name}`} question="Which aircraft can fly, and what needs attention now?"
        right={<>
          {d.squadrons?.length > 0 && (
            <select className="input w-auto" aria-label="Squadron" value={d.squadron} onChange={(e) => setSq(e.target.value)}>
              {d.squadrons.map((s: any) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          )}
          <Button variant="outline" size="sm" onClick={() => run("pdf", () => download(`/reports/readiness.pdf${q}`, `readiness-${d.squadron}.pdf`))}>Report PDF</Button>
          <Button variant="outline" size="sm" onClick={() => run("csv", () => download(`/reports/readiness.csv${q}`, `readiness-${d.squadron}.csv`))}>Report CSV</Button>
        </>} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Fleet Health Score" sub="100 minus the points lost on 5 rules" />
          <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
            <div className="text-center sm:w-36">
              <div className={cn("text-6xl font-bold leading-none", scoreTone)} data-testid="fleet-score">{d.score}</div>
              <div className="text-xs text-slate-500">out of 100</div>
            </div>
            <ul className="flex-1 space-y-1.5">
              {d.rules.map((r: any) => (
                <li key={r.key} className="flex items-start justify-between gap-3 text-sm">
                  <Link href={r.link} className="min-w-0 hover:underline">
                    <span className="font-medium text-slate-700">{r.label}</span>
                    <span className="block text-xs text-slate-500">{r.detail}</span>
                  </Link>
                  <span className={cn("w-10 shrink-0 text-right font-semibold", r.points < 0 ? "text-crit" : "text-ok")}>{r.points === 0 ? "0" : r.points}</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card>
          <CardHeader title="Needs attention now" sub={`${d.alerts.length} open alert${d.alerts.length === 1 ? "" : "s"}, most urgent first`} right={<Link href="/alerts" className="text-xs text-sky-700 hover:underline">All alerts</Link>} />
          {d.alerts.length === 0 ? <Empty>Nothing needs attention right now.</Empty> : (
            <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto">
              {d.alerts.map((a: any) => (
                <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge tone={severityTone(a.severity)}>{a.severity}</Badge>
                      <span className="text-sm font-medium">{a.tail_no}</span>
                      <span className="text-xs text-slate-400">{a.id}</span>
                      {a.overdue && <Badge tone="red">Review overdue {Math.abs(a.hours_left).toFixed(0)} h</Badge>}
                      {a.escalated && <Badge tone="red">Escalated</Badge>}
                    </div>
                    <div className="truncate text-xs text-slate-600">{a.message}</div>
                  </div>
                  {me?.role === "ENGO" && (a.kind === "RUL" || a.kind === "ANOMALY")
                    ? <Button size="sm" onClick={() => setReview(a)}>Review</Button>
                    : <Button size="sm" variant="outline" onClick={() => router.push(a.action_link)}>Open</Button>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Mission-capable today" value={`${k.mission_capable}/${k.total}`} tone={k.mission_capable / k.total >= k.availability_target ? "green" : "amber"} />
        <Stat label={`Forecast in ${k.forecast_day} days`} value={`${k.forecast_mission_capable}/${k.total}`} sub="without further action" tone={k.forecast_mission_capable / k.total >= k.availability_target ? "green" : "red"} />
        <Stat label="Aircraft on ground (AOG)" value={k.aog} sub={`${k.aog_awaiting_spares} awaiting spares · ${k.in_maintenance} in maintenance`} tone={k.aog ? "amber" : "green"} />
        <Stat label="Critical alerts" value={k.critical_alerts} sub={`${k.critical_unreviewed} awaiting review`} tone={k.critical_alerts ? "red" : "green"} />
        <Stat label="Combat-ready" value={k.combat_ready} sub="all systems working" />
        <Stat label="Transport-ready" value={k.transport_ready} sub="engines, controls, gear" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="30-day readiness forecast" sub={d.forecast.summary}
            right={me?.role === "CO" && !d.forecast.plan_approved && d.forecast.plan_tasks.length > 0
              ? <Button size="sm" variant="success" busy={busy === "approve"} onClick={() => run("approve", () => api("/schedule/approve", { method: "POST" }), reload)}>Approve plan</Button>
              : d.forecast.plan_approved && d.forecast.plan_tasks.length === 0 ? <Badge tone="green">Plan approved</Badge>
              : <Link href="/schedule" className="text-xs text-sky-700 hover:underline">Open schedule</Link>} />
          <div className="p-3">
            <ForecastChart days={d.forecast.days} without={d.forecast.without} withPlan={d.forecast.with_plan} total={d.forecast.total} target={k.availability_target}
              withLabel={d.forecast.plan_approved && d.forecast.plan_tasks.length === 0 ? "With approved plan" : "With recommended plan"} />
            {d.forecast.plan_tasks.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">Recommended plan: {d.forecast.plan_tasks.map((t: any) => `${t.tail} (day ${t.start_day})`).join(", ")}.</p>
            )}
            <div className="mt-2"><Advisory /></div>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Aircraft by health" sub="Tap an aircraft to open its digital twin" />
          <div className="grid grid-cols-3 gap-2 p-3 sm:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4">
            {d.aircraft.map((a: any) => (
              <Link key={a.tail_no} href={`/aircraft/${a.tail_no}`} className={cn("rounded-md border p-2 text-center hover:shadow", healthBg(a.health_score))}>
                <div className="text-xs font-semibold text-slate-800">{a.tail_no.replace("TAIL-", "")}</div>
                <div className="text-lg font-semibold leading-tight">{a.health_score}</div>
                <div className="text-[10px] text-slate-600">{a.status_label}</div>
              </Link>
            ))}
          </div>
          <div className="flex flex-wrap gap-3 border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-green-500" />Health 60+ OK</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />30–59 warning</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />under 30 critical</span>
          </div>
        </Card>
      </div>

      {review && <ReviewDialog alert={review} onClose={() => setReview(null)} onDone={() => { setReview(null); reload(); }} />}
    </div>
  );
}
