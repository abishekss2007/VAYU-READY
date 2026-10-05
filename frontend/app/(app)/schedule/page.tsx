"use client";
import { useRef, useState } from "react";
import { ForecastChart } from "@/components/forecast-chart";
import { Advisory, Badge, Button, Card, CardHeader, cn, Empty, ErrorBox, Loading, PageTitle, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

const DAYS = 30;

export default function Schedule() {
  const { me, tick, notify } = useSession();
  const canPlan = me?.role === "ENGO" || me?.role === "CO";
  const canWhatIf = canPlan || me?.role === "FSO";
  const cal = useLoad(() => api("/schedule"), [tick]);
  const [plan, setPlan] = useState<any>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const { busy, run } = useAction();
  const drag = useRef<string | null>(null);

  const optimise = () => run("opt", () => api("/schedule/optimise", { method: "POST" }), (r) => { setPlan(r); setSelected(null); });
  const move = async (tail: string, startDay: number) => {
    if (!plan) return;
    const tasks = plan.tasks.map((t: any) => ({ tail: t.tail, start_day: t.tail === tail ? Math.max(0, Math.min(DAYS - 1, startDay)) : t.start_day }));
    try {
      const r = await api("/schedule/check", { body: { tasks } });
      setPlan(r);
      if (r.problems.length) notify(r.problems[0].message, "error");
    } catch (e: any) { notify(e.message, "error"); }
  };
  const approve = () => run("approve", () => api("/schedule/approve", { body: { tasks: plan.tasks.map((t: any) => ({ tail: t.tail, start_day: t.start_day })) } }), () => { setPlan(null); cal.reload(); });

  if (cal.loading && !cal.data) return <Loading label="Loading schedule..." />;
  if (cal.error) return <ErrorBox>{cal.error}</ErrorBox>;
  const committed = cal.data.tasks;
  const proposed = plan?.tasks || [];
  const hangars = Array.from(new Set(["Hangar 1", "Hangar 2", ...committed.map((t: any) => t.hangar), ...proposed.map((t: any) => t.hangar)])) as string[];
  const sel = proposed.find((t: any) => t.tail === selected);

  return (
    <div>
      <PageTitle title="Maintenance Schedule and What-If" question="When should each aircraft go into the hangar to keep the most aircraft flying?"
        right={canPlan && <>
          <Button busy={busy === "opt"} onClick={optimise}>Run optimiser</Button>
          {me?.role === "CO" && plan && <Button variant="success" busy={busy === "approve"} disabled={!plan.can_approve || !proposed.length} onClick={approve}>Approve plan</Button>}
        </>} />

      <Card>
        <CardHeader title={`Next ${DAYS} days by hangar`} sub={`Base hangar capacity: 2 aircraft per day · 10 technicians × 8 h. ${plan ? "Blue = proposed (drag to move, or select and use Earlier / Later). " : ""}Grey = already in the schedule.`}
          right={cal.data.plan_approved && !plan ? <Badge tone="green">Plan approved</Badge> : plan ? <Badge tone="blue">Proposed, not saved</Badge> : null} />
        <div className="overflow-x-auto p-3">
          <div className="min-w-[860px]">
            <div className="grid" style={{ gridTemplateColumns: `7rem repeat(${DAYS}, minmax(0, 1fr))` }}>
              <div className="text-[10px] font-medium text-slate-500">Day</div>
              {Array.from({ length: DAYS }, (_, d) => <div key={d} className={cn("border-l border-slate-100 text-center text-[10px]", d % 7 === 0 ? "font-semibold text-navy" : "text-slate-400")}>{d}</div>)}
            </div>
            {hangars.map((h) => (
              <div key={h} className="grid border-t border-slate-200" style={{ gridTemplateColumns: "7rem 1fr" }}>
                <div className="py-2 text-xs font-medium text-slate-700">{h}</div>
                <div className="relative grid min-h-[2.75rem] gap-y-1 py-1" style={{ gridTemplateColumns: `repeat(${DAYS}, minmax(0, 1fr))`, backgroundImage: "linear-gradient(to right, #f1f5f9 1px, transparent 1px)", backgroundSize: `${100 / DAYS}% 100%` }}
                  onDragOver={(e) => plan && e.preventDefault()}
                  onDrop={(e) => {
                    if (!drag.current) return;
                    const r = e.currentTarget.getBoundingClientRect();
                    move(drag.current, Math.floor(((e.clientX - r.left) / r.width) * DAYS));
                    drag.current = null;
                  }}>
                  {committed.filter((t: any) => t.hangar === h && t.duration > 0 && t.start_day < DAYS).map((t: any) => (
                    <div key={`c${t.id}`} title={`${t.tail_no}: ${t.title}`} className="truncate rounded bg-slate-200 px-1.5 py-1 text-[11px] text-slate-700"
                      style={{ gridColumn: `${t.start_day + 1} / span ${Math.min(t.duration, DAYS - t.start_day)}` }}>{t.tail_no.replace("TAIL-", "")} · {t.title}</div>
                  ))}
                  {proposed.filter((t: any) => t.hangar === h).map((t: any) => (
                    <button key={`p${t.tail}`} draggable onDragStart={() => { drag.current = t.tail; }} onClick={() => setSelected(t.tail)} title={t.title}
                      className={cn("cursor-grab truncate rounded px-1.5 py-1 text-left text-[11px] text-white", t.late ? "bg-amber-600" : "bg-sky-600", selected === t.tail && "ring-2 ring-navy")}
                      style={{ gridColumn: `${t.start_day + 1} / span ${Math.min(t.duration, DAYS - t.start_day)}` }}>{t.tail.replace("TAIL-", "")}</button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        {sel && (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-2 text-sm">
            <span className="font-medium">{sel.tail}</span><span className="text-slate-600">{sel.title}</span>
            <span className="text-xs text-slate-500">starts day {sel.start_day}, {sel.duration} day(s){sel.part_no ? `, part ${sel.part_no} arrives day ${sel.earliest}` : ""}{sel.deadline != null ? `, safe until day ${sel.deadline}` : ""}</span>
            <Button size="sm" variant="outline" onClick={() => move(sel.tail, sel.start_day - 1)}>Earlier</Button>
            <Button size="sm" variant="outline" onClick={() => move(sel.tail, sel.start_day + 1)}>Later</Button>
          </div>
        )}
        {!plan && committed.length === 0 && <Empty>Nothing is scheduled yet.</Empty>}
      </Card>

      {plan && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Proposed plan" sub={plan.summary} />
            <div className="space-y-2 p-4 text-sm">
              {plan.problems.map((p: any, i: number) => <div key={i} className={cn("rounded border px-3 py-2 text-xs", p.blocking ? "border-red-200 bg-red-50 text-red-700" : "border-amber-200 bg-amber-50 text-amber-800")}>{p.blocking ? "Not allowed: " : "Warning: "}{p.message}</div>)}
              {proposed.length === 0 ? <Empty>No maintenance is waiting to be planned.</Empty> : (
                <ul className="divide-y divide-slate-100">
                  {proposed.map((t: any) => (
                    <li key={t.tail} className="py-1.5">
                      <span className="font-medium">{t.tail}</span> · {t.hangar} · day {t.start_day}–{t.start_day + t.duration - 1} {t.late && <Badge tone="amber">Part arrives late: stand-down from day {t.deadline}</Badge>}
                      <div className="text-xs text-slate-500">{t.title}</div>
                    </li>
                  ))}
                </ul>
              )}
              {plan.unscheduled.map((u: any) => <div key={u.tail} className="text-xs text-amber-700">Not scheduled: {u.tail} ({u.title}). {u.reason}.</div>)}
              <p className="text-xs text-slate-500">Assumptions: {plan.assumptions.sorties_per_day} sorties/day, {plan.assumptions.safety_margin_days}-day safety margin, engine change {plan.assumptions.engine_change_days} days. Solved in {plan.solve_seconds ?? "<1"} s.</p>
              {me?.role !== "CO" && <p className="text-xs text-slate-500">Only the Squadron Commander can approve the plan.</p>}
              <Advisory />
            </div>
          </Card>
          <Card>
            <CardHeader title="Readiness forecast" sub="Mission-capable aircraft per day" />
            <div className="p-3"><ForecastChart days={plan.forecast.days} without={plan.forecast.without} withPlan={plan.forecast.with_plan} total={plan.forecast.total} withLabel="With this plan" /></div>
          </Card>
        </div>
      )}

      {canWhatIf && <WhatIf squadron={cal.data.squadron} />}
    </div>
  );
}

function WhatIf({ squadron }: { squadron: string }) {
  const aircraft = useLoad(() => api(`/aircraft?squadron=${squadron}`), [squadron]);
  const parts = useLoad(() => api("/parts"), []);
  const [service, setService] = useState<string[]>([]);
  const [expedite, setExpedite] = useState<string[]>([]);
  const [sorties, setSorties] = useState("1.2");
  const [res, setRes] = useState<any>(null);
  const { busy, run } = useAction();
  const toggle = (list: string[], set: (v: string[]) => void, v: string) => set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const short = (parts.data || []).filter((p: any) => p.stock === 0);
  // aircraft worth servicing first: lowest health or not mission-capable
  const candidates = (aircraft.data || []).filter((a: any) => a.status !== "MC" || a.health_score < 60 || service.includes(a.tail_no)).slice(0, 12);

  return (
    <Card className="mt-4">
      <CardHeader title="What-if simulator" sub="“If we service these aircraft this week, what is the 30-day availability?” Nothing is saved." />
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div>
            <div className="label">Aircraft to service now</div>
            {aircraft.loading ? <Loading /> : candidates.length === 0 ? <Empty>No aircraft need servicing.</Empty> : (
              <div className="flex flex-wrap gap-1.5">
                {candidates.map((a: any) => (
                  <button key={a.tail_no} onClick={() => toggle(service, setService, a.tail_no)}
                    className={cn("min-h-[36px] rounded-md border px-2.5 text-xs", service.includes(a.tail_no) ? "border-sky-500 bg-sky-50 font-medium text-sky-800" : "border-slate-300")}>{a.tail_no.replace("TAIL-", "")} · {a.status_label}</button>
                ))}
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label" htmlFor="spd">Sorties per day (cycles)</label>
              <input id="spd" className="input" type="number" step="0.1" min="0.2" max="6" value={sorties} onChange={(e) => setSorties(e.target.value)} /></div>
            <div><div className="label">Expedite a part (arrives in 2 days)</div>
              <div className="flex flex-wrap gap-1.5">
                {short.length === 0 ? <span className="text-xs text-slate-500">No part is out of stock.</span> : short.map((p: any) => (
                  <button key={p.part_no} onClick={() => toggle(expedite, setExpedite, p.part_no)}
                    className={cn("min-h-[36px] rounded-md border px-2 text-xs", expedite.includes(p.part_no) ? "border-sky-500 bg-sky-50 font-medium text-sky-800" : "border-slate-300")}>{p.part_no}</button>
                ))}
              </div></div>
          </div>
          <Button busy={busy === "wi"} onClick={() => run("wi", () => api("/whatif", { body: { squadron, service, horizon_days: 30, sorties_per_day: Number(sorties) || 1.2, expedite } }), setRes)}>Run what-if</Button>
          {res && (
            <div className="rounded-md border border-sky-200 bg-sky-50 p-3">
              <div className="text-lg font-semibold text-navy">{res.message.replace("->", "→")}</div>
              <div className="text-xs text-slate-600">Day 30: combat-ready {res.combat_without[30]} → {res.combat_with[30]}, transport-ready {res.transport_without[30]} → {res.transport_with[30]}. Computed in {res.seconds} s.</div>
              {res.tasks.map((t: any) => <div key={t.tail} className="text-xs text-slate-600">{t.tail}: day {t.start_day}–{t.start_day + t.duration - 1}, {t.title}</div>)}
            </div>
          )}
          <Advisory />
        </div>
        <div>{res ? <ForecastChart days={res.days} without={res.without} withPlan={res.with} total={res.total} withLabel="With this what-if" /> : <Empty>Choose aircraft and run the what-if to see the forecast.</Empty>}</div>
      </div>
    </Card>
  );
}
