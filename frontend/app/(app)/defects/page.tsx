"use client";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, Modal, PageTitle, TableWrap, useLoad } from "@/components/ui";
import { api, fmtDate, fmtTime } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

const CATEGORIES = ["Engine", "Hydraulics", "Avionics", "Landing gear", "Fuel", "Electrical", "Airframe", "Environmental control"];
const TASK_TONE: Record<string, string> = { Scheduled: "blue", Done: "amber", SignedOff: "green" };
const TASK_LABEL: Record<string, string> = { Scheduled: "To do", Done: "Done, awaiting sign-off", SignedOff: "Signed off" };

export default function DefectsAndTasks() {
  const { me, tick } = useSession();
  const tech = me?.role === "TECH", engo = me?.role === "ENGO";
  const canLog = tech || engo;
  const tasks = useLoad(() => api(`/tasks${tech ? "?mine=true" : ""}`), [tick, tech]);
  const defects = useLoad(() => api("/defects"), [tick]);
  const aircraft = useLoad(() => (canLog ? api("/aircraft") : Promise.resolve([])), [canLog]);
  const { busy, run } = useAction();
  const [tail, setTail] = useState("");
  const [text, setText] = useState("");
  const [suggest, setSuggest] = useState<any>(null);
  const [category, setCategory] = useState("");
  const [complete, setComplete] = useState<any>(null);
  const [hours, setHours] = useState("2");
  const reloadAll = () => { tasks.reload(); defects.reload(); };

  return (
    <div>
      <PageTitle title={tech ? "My tasks" : "Defects and Tasks"} question={tech ? "What do I need to do today?" : "What work is open, and what is waiting for sign-off?"} />

      <Card className="mb-4">
        <CardHeader title={tech ? "Today's tasks" : "Maintenance tasks"} sub="A task is closed by the technician who did it and signed off by an Engineering Officer (two different people)" />
        {tasks.error ? <div className="p-3"><ErrorBox>{tasks.error}</ErrorBox></div> : tasks.loading && !tasks.data ? <Loading /> : !tasks.data?.length ? <Empty>No tasks assigned.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Aircraft</th><th className="th">Task</th><th className="th">Slot</th><th className="th">Where</th><th className="th">Status</th><th className="th">Action</th></tr></thead>
            <tbody>
              {tasks.data.map((t: any) => (
                <tr key={t.id} className="border-b border-slate-100">
                  <td className="td font-medium">{t.tail_no}</td>
                  <td className="td">{t.title}{t.part_no && <div className="text-xs text-slate-500">Part {t.part_no}</div>}</td>
                  <td className="td whitespace-nowrap text-xs">{fmtDate(t.slot_start)} – {fmtDate(t.slot_end)}</td>
                  <td className="td text-xs">{t.hangar}<div className="text-slate-500">{t.assigned_to || "Unassigned"}</div></td>
                  <td className="td"><Badge tone={TASK_TONE[t.status]}>{TASK_LABEL[t.status]}</Badge>{t.hours_spent != null && <div className="mt-1 text-xs text-slate-500">{t.hours_spent} h by {t.completed_by}</div>}</td>
                  <td className="td whitespace-nowrap">
                    {tech && t.status === "Scheduled" && <Button size="sm" onClick={() => { setComplete(t); setHours("2"); }}>Mark done</Button>}
                    {engo && t.status === "Done" && <Button size="sm" variant="success" busy={busy === `s${t.id}`} onClick={() => run(`s${t.id}`, () => api(`/tasks/${t.id}/signoff`, { method: "POST" }), reloadAll)}>Sign off</Button>}
                    {!((tech && t.status === "Scheduled") || (engo && t.status === "Done")) && <span className="text-xs text-slate-400">{t.status === "SignedOff" ? `Signed off by ${t.signed_off_by}` : t.status === "Done" ? "Waiting for ENGO" : "Waiting for technician"}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>

      {canLog && (
        <Card className="mb-4">
          <CardHeader title="Log a defect" sub="Type what you see in your own words. The system suggests a category; you confirm it." />
          <div className="grid gap-3 p-4 md:grid-cols-[14rem_1fr_auto] md:items-end">
            <div><label className="label" htmlFor="tail">Aircraft</label>
              <select id="tail" className="input" value={tail} onChange={(e) => setTail(e.target.value)}>
                <option value="">Choose aircraft</option>
                {(aircraft.data || []).map((a: any) => <option key={a.tail_no}>{a.tail_no}</option>)}
              </select></div>
            <div><label className="label" htmlFor="dtext">Defect (free text)</label>
              <input id="dtext" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. hyd leak near left MLG actuator" /></div>
            <Button busy={busy === "log"} disabled={!tail || text.trim().length < 3}
              onClick={() => run("log", () => api("/defects", { body: { tail_no: tail, text } }), (r) => { setSuggest(r); setCategory(r.suggested_category); setText(""); reloadAll(); })}>Log defect</Button>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Defect log" sub="Newest first. Records are never deleted." />
        {defects.error ? <div className="p-3"><ErrorBox>{defects.error}</ErrorBox></div> : defects.loading && !defects.data ? <Loading /> : !defects.data?.length ? <Empty>No defects logged.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Aircraft</th><th className="th">Defect</th><th className="th">System</th><th className="th">Logged</th><th className="th">Status</th></tr></thead>
            <tbody>
              {defects.data.map((d: any) => (
                <tr key={d.id} className="border-b border-slate-100">
                  <td className="td font-medium">{d.tail_no}</td>
                  <td className="td">{d.text}</td>
                  <td className="td"><Badge>{d.confirmed_category || d.suggested_category}</Badge>{!d.confirmed_category && <div className="mt-1 text-xs text-amber-700">Suggested, not confirmed</div>}</td>
                  <td className="td whitespace-nowrap text-xs">{fmtTime(d.logged_at)}<div className="text-slate-500">{d.logged_by}</div></td>
                  <td className="td"><Badge tone={d.status === "Open" ? "amber" : "green"}>{d.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>

      {suggest && (
        <Modal title="Confirm the defect category" onClose={() => setSuggest(null)}>
          <div className="space-y-3 text-sm">
            <p>“{suggest.defect.text}” on <b>{suggest.defect.tail_no}</b></p>
            <p>Suggested: <Badge tone="blue">{suggest.suggestion}</Badge>{suggest.confidence != null && <span className="ml-2 text-xs text-slate-500">confidence {(suggest.confidence * 100).toFixed(0)}%</span>}</p>
            {suggest.recurring_alert && <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">This is the 3rd similar defect in 30 days on this aircraft. A recurring-defect alert was raised.</p>}
            <div><label className="label" htmlFor="cat">Category</label>
              <select id="cat" className="input" value={category} onChange={(e) => setCategory(e.target.value)}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></div>
            <p className="text-xs text-slate-500">{suggest.advisory}</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSuggest(null)}>Later</Button>
              <Button busy={busy === "confirm"} onClick={() => run("confirm", () => api(`/defects/${suggest.defect.id}/confirm`, { body: { category } }), () => { setSuggest(null); reloadAll(); })}>Confirm</Button>
            </div>
          </div>
        </Modal>
      )}

      {complete && (
        <Modal title={`Mark done · ${complete.tail_no}`} onClose={() => setComplete(null)}>
          <div className="space-y-3 text-sm">
            <p>{complete.title}</p>
            <div><label className="label" htmlFor="hrs">Hours spent</label>
              <input id="hrs" className="input" type="number" min="0.5" step="0.5" value={hours} onChange={(e) => setHours(e.target.value)} /></div>
            <p className="text-xs text-slate-500">An Engineering Officer must sign this off before the aircraft is released.</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setComplete(null)}>Cancel</Button>
              <Button busy={busy === "done"} disabled={!(Number(hours) > 0)} onClick={() => run("done", () => api(`/tasks/${complete.id}/complete`, { body: { hours_spent: Number(hours) } }), () => { setComplete(null); reloadAll(); })}>Mark done</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
