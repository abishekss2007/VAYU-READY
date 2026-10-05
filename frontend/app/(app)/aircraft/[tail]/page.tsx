"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ReviewDialog } from "@/components/review-dialog";
import { Advisory, Badge, Button, Card, CardHeader, Empty, ErrorBox, healthTone, Loading, Modal, PageTitle, severityTone, statusTone, useLoad } from "@/components/ui";
import { api, fmtDate, fmtTime } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

const LIVE_LABEL: Record<string, string> = { s3: "HPC outlet temp", s4: "LPT outlet temp", s8: "Fan speed", s11: "HPC static pressure" };

export default function Twin() {
  const { tail } = useParams<{ tail: string }>();
  const { me, tick } = useSession();
  const { data: t, error, loading, reload } = useLoad(() => api(`/aircraft/${tail}/twin`), [tick, tail]);
  const [review, setReview] = useState<any>(null);
  const [reviewed, setReviewed] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [live, setLive] = useState<Record<string, any>>({});
  const { busy, run } = useAction();
  const engo = me?.role === "ENGO";

  useEffect(() => {
    const h = (e: any) => { if (e.detail.tail_no === tail) setLive((l) => ({ ...l, [e.detail.engine_id]: e.detail })); };
    window.addEventListener("vayu-sensor", h);
    return () => window.removeEventListener("vayu-sensor", h);
  }, [tail]);

  if (loading && !t) return <Loading label="Loading digital twin..." />;
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!t) return null;
  const openAlerts = t.alerts.filter((a: any) => !a.reviewed_at);

  return (
    <div>
      <PageTitle title={`${t.tail_no} · digital twin`} question={`${t.type} · ${t.squadron_code} · ${t.flying_hours.toLocaleString()} flying hours · updated ${fmtTime(t.updated_at)}`}
        right={<>
          <Badge tone={statusTone(t.status)}>{t.status_label}</Badge><Badge>{t.readiness}</Badge>
          {engo && <Button size="sm" variant="outline" onClick={() => setStatusOpen(true)}>Change status</Button>}
          <Link href="/aircraft" className="text-xs text-sky-700 hover:underline">Back to list</Link>
        </>} />

      {openAlerts.length > 0 && (
        <Card className="mb-4 border-red-200">
          <ul className="divide-y divide-slate-100">
            {openAlerts.map((a: any) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
                <div className="min-w-0 text-sm">
                  <Badge tone={severityTone(a.severity)}>{a.severity}</Badge> <span className="font-medium">{a.id}</span> {a.message}
                  {a.hours_left != null && <span className={a.overdue ? "ml-2 font-medium text-crit" : "ml-2 text-slate-500"}>{a.overdue ? `Review overdue by ${Math.abs(a.hours_left).toFixed(0)} h` : `${a.hours_left.toFixed(0)} h left to review`}</span>}
                </div>
                {engo ? <Button size="sm" onClick={() => setReview(a)}>Review alert</Button> : <Link href="/alerts" className="inline-flex min-h-[32px] items-center rounded-md border border-slate-300 px-2.5 text-xs font-medium">Open alerts</Link>}
              </li>
            ))}
          </ul>
        </Card>
      )}
      {reviewed && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-800">
          Review saved. Next step: put the fix in the plan.
          <Link href="/schedule" className="inline-flex min-h-[32px] items-center rounded-md bg-ok px-3 text-xs font-medium text-white">Open schedule</Link>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Aircraft health score" sub="0–100, higher is better" />
          <div className="p-4">
            <div className={`text-5xl font-bold ${healthTone(t.health.score) === "green" ? "text-ok" : healthTone(t.health.score) === "amber" ? "text-warn" : "text-crit"}`}>{t.health.score}<span className="ml-1 text-base font-medium text-slate-500">/ 100</span></div>
            <ul className="mt-3 space-y-1 text-sm">
              {t.health.lines.map((l: any) => <li key={l.label} className="flex justify-between"><span>{l.label}</span><span className="font-medium">{l.points > 0 ? l.points : l.points}</span></li>)}
            </ul>
            <p className="mt-3 rounded bg-slate-50 p-2 text-xs text-slate-600"><b>Formula:</b> {t.health.formula}.</p>
          </div>
        </Card>
        <Card>
          <CardHeader title="Next maintenance due" />
          <div className="p-4 text-sm">
            {t.next_maintenance_due ? <><div className="text-2xl font-semibold text-navy">{fmtDate(t.next_maintenance_due)}</div><div className="text-slate-600">{t.next_maintenance_title}</div></> : <span className="text-slate-500">No task in the schedule.</span>}
            <div className="mt-3 text-xs font-medium text-slate-500">Open defects: {t.open_defects.length}</div>
            <ul className="mt-1 space-y-1 text-xs text-slate-600">{t.open_defects.map((d: any) => <li key={d.id}>• {d.text} <Badge>{d.confirmed_category || d.suggested_category}</Badge></li>)}</ul>
          </div>
        </Card>
        <Card>
          <CardHeader title="Spares status" />
          {t.spares.length === 0 ? <Empty>No parts on order for this aircraft.</Empty> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {t.spares.map((s: any) => (
                <li key={s.id} className="px-4 py-2">
                  <div className="font-medium">{s.part_name} ({s.part_no}) <Badge tone={s.status === "Received" ? "green" : s.late ? "red" : "amber"}>{s.status}</Badge></div>
                  <div className={`text-xs ${s.late ? "text-crit" : "text-slate-500"}`}>{s.id} · stock {s.stock} · lead time {s.lead_time_days} days · {s.status === "Received" ? "received" : `arrives in ${s.arrives_in_days} days, needed in ${s.needed_in_days} days`}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {t.engines.length === 0 && <Card><Empty>No engine records for this aircraft yet.</Empty></Card>}
        {t.engines.map((e: any) => {
          const lv = live[e.id];
          return (
            <Card key={e.id} className={e.critical ? "border-red-300" : ""}>
              <CardHeader title={`Engine ${e.position} · ${e.id}`} sub={`Serial ${e.serial}`}
                right={engo && <Button size="sm" variant="outline" busy={busy === e.id} onClick={() => run(e.id, () => api(`/predict/${e.id}`, { method: "POST" }), reload)}>Run prediction</Button>} />
              <div className="grid grid-cols-3 gap-3 px-4 pt-3 text-center">
                <div><div className="text-xs text-slate-500">Remaining useful life</div><div className={`text-2xl font-semibold ${e.critical ? "text-crit" : "text-navy"}`}>{e.rul_cycles?.toFixed(0) ?? "-"}</div><div className="text-xs text-slate-500">cycles (about {e.rul_days ?? "-"} days)</div></div>
                <div><div className="text-xs text-slate-500">Anomaly score (0–1)</div><div className={`text-2xl font-semibold ${e.anomaly_flag ? "text-warn" : "text-navy"}`}>{e.anomaly_score?.toFixed(2) ?? "-"}</div><div className="text-xs text-slate-500">{e.anomaly_flag ? "unusual pattern" : "normal"}</div></div>
                <div><div className="text-xs text-slate-500">Hours to overhaul</div><div className={`text-2xl font-semibold ${e.hours_left <= 10 ? "text-crit" : e.hours_left <= 50 ? "text-warn" : "text-navy"}`}>{e.hours_left}</div><div className="text-xs text-slate-500">of {e.overhaul_limit_hours} h limit</div></div>
              </div>
              <div className="h-44 px-2 pt-3" aria-label="RUL trend">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={e.rul_history.map((h: any, i: number) => ({ i, rul: h.rul, time: fmtDate(h.time) }))} margin={{ top: 4, right: 12, bottom: 4, left: -12 }}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} domain={[0, "auto"]} />
                    <Tooltip formatter={(v: any) => [`${v} cycles`, "RUL"]} />
                    <ReferenceLine y={25} stroke="#dc2626" strokeDasharray="5 4" label={{ value: "Critical: 25", fontSize: 10, fill: "#dc2626", position: "insideBottomRight" }} />
                    <Line dataKey="rul" stroke="#0ea5e9" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="px-4 pb-3">
                <div className="mt-2 text-xs font-medium text-slate-500">Why (top 3 sensors, SHAP)</div>
                {e.shap_top3.length === 0 ? <div className="text-xs text-slate-500">No explanation stored for this prediction.</div> : (
                  <ul className="mt-1 space-y-1 text-sm">
                    {e.shap_top3.map((s: any) => <li key={s.sensor} className="flex justify-between"><span>{s.text} <span className="text-xs text-slate-400">({s.sensor})</span></span><span className={s.impact_cycles < 0 ? "text-crit" : "text-ok"}>{s.impact_cycles > 0 ? "+" : ""}{s.impact_cycles} cycles</span></li>)}
                  </ul>
                )}
                <div className="mt-3 text-xs font-medium text-slate-500">Latest sensor snapshot {lv ? <Badge tone="green">live · cycle {lv.cycle}</Badge> : e.latest_sensors ? `· cycle ${e.latest_sensors.cycle}` : ""}</div>
                <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs sm:grid-cols-4">
                  {Object.keys(LIVE_LABEL).map((s) => <div key={s} className="flex justify-between gap-1"><span className="text-slate-500">{LIVE_LABEL[s]}</span><span className="font-medium">{(lv?.values?.[s] ?? e.latest_sensors?.[s])?.toFixed?.(2) ?? "-"}</span></div>)}
                </div>
                <p className="mt-3 text-[11px] text-slate-400">Model {e.model_version || "-"} · data {e.model_dataset || "-"} · trained {e.model_trained_on || "-"} · test RMSE {e.model_test_rmse ?? "-"}</p>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="mt-4"><Advisory /></div>

      {review && <ReviewDialog alert={review} onClose={() => setReview(null)} onDone={(_, decision) => { setReview(null); setReviewed(decision !== "FalseAlarm"); reload(); }} />}
      {statusOpen && <StatusDialog tail={t.tail_no} current={t.status} onClose={() => setStatusOpen(false)} onDone={() => { setStatusOpen(false); reload(); }} />}
    </div>
  );
}

function StatusDialog({ tail, current, onClose, onDone }: { tail: string; current: string; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState(current === "MC" ? "MAINT" : "MC");
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  return (
    <Modal title={`Change status · ${tail}`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-xs text-slate-500">Only an Engineering Officer changes aircraft status. No model output can do this.</p>
        <div><label className="label" htmlFor="st">New status</label>
          <select id="st" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="MC">Mission-capable</option><option value="PMC">Partially capable</option><option value="AOG">AOG</option><option value="MAINT">In maintenance</option>
          </select></div>
        <div><label className="label" htmlFor="rs">Reason (required)</label>
          <textarea id="rs" className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: MLG actuator fitted and tested" /></div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button busy={busy === "st"} disabled={reason.trim().length < 3} onClick={() => run("st", () => api(`/aircraft/${tail}/status`, { method: "PATCH", body: { status, reason } }), onDone)}>Save status</Button>
        </div>
      </div>
    </Modal>
  );
}
