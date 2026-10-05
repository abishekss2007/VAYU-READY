"use client";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, Stat, TableWrap, useLoad } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

export default function Overhaul() {
  const { me, tick } = useSession();
  const [days, setDays] = useState(90);
  const { data, error, loading, reload } = useLoad(() => api(`/overhaul?days=${days}`), [tick, days]);
  const { busy, run } = useAction();
  const canRecord = me?.role === "ENGO" || me?.role === "BRD";
  const tone = (l: string) => (l === "Critical" ? "red" : l === "Warning" ? "amber" : "green");

  return (
    <div>
      <PageTitle title="Overhaul Tracker" question="Which engines reach their overhaul limit soon, and is depot capacity planned?"
        right={<select className="input w-auto" aria-label="Window" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={30}>Next 30 days</option><option value={90}>Next 90 days</option><option value={180}>Next 180 days</option>
        </select>} />
      {error && <ErrorBox>{error}</ErrorBox>}
      {loading && !data ? <Loading /> : data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label="Engines due within 30 days" value={data.due_within_30_days} tone={data.due_within_30_days ? "amber" : "green"} />
            <Stat label={`Engines due within ${days} days`} value={data.engines.length} />
            <Stat label="Engines past limit (safety flag)" value={data.past_limit} tone={data.past_limit ? "red" : "green"} sub={data.past_limit ? "Aircraft locked as not mission-capable" : "None"} />
          </div>
          <Card className="mb-4">
            <CardHeader title="Timeline" sub={`Each bar ends on the day the engine reaches its limit (at ${data.flying_hours_per_day} flying hours per day)`} />
            {data.engines.length === 0 ? <Empty>No engines due in this window.</Empty> : (
              <div className="space-y-1.5 p-4">
                {data.engines.map((e: any) => (
                  <div key={e.engine_id} className="grid grid-cols-[8.5rem_1fr_4.5rem] items-center gap-2 text-xs">
                    <span className="font-medium">{e.engine_id} <span className="font-normal text-slate-500">{e.squadron_code}</span></span>
                    <div className="h-4 rounded bg-slate-100"><div className={`h-4 rounded ${e.level === "Critical" ? "bg-red-500" : e.level === "Warning" ? "bg-amber-500" : "bg-sky-500"}`} style={{ width: `${Math.max((e.due_in_days / days) * 100, 2)}%` }} /></div>
                    <span className="text-right text-slate-600">{e.due_in_days} days</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <Card>
            <CardHeader title="Engines" sub={data.note + " Reminders are raised at 50, 25 and 10 hours left."} />
            {data.engines.length === 0 ? <Empty>No engines due in this window.</Empty> : (
              <TableWrap>
                <thead><tr className="border-b border-slate-200"><th className="th">Engine</th><th className="th">Aircraft</th><th className="th">Hours since overhaul</th><th className="th">Limit</th><th className="th">Hours left</th><th className="th">Due</th><th className="th">Action</th></tr></thead>
                <tbody>
                  {data.engines.map((e: any) => (
                    <tr key={e.engine_id} className="border-b border-slate-100">
                      <td className="td font-medium">{e.engine_id}<div className="text-xs font-normal text-slate-500">{e.serial}</div></td>
                      <td className="td">{e.tail_no}<div className="text-xs text-slate-500">{e.squadron_code}</div></td>
                      <td className="td">{e.hours_since_overhaul} h</td><td className="td">{e.overhaul_limit_hours} h</td>
                      <td className="td"><Badge tone={tone(e.level)}>{e.past_limit ? "Past limit" : `${e.hours_left} h`}</Badge></td>
                      <td className="td whitespace-nowrap text-xs">{fmtDate(e.due_date)} ({e.due_in_days} days)</td>
                      <td className="td">{canRecord ? <Button size="sm" variant="outline" busy={busy === e.engine_id} onClick={() => confirm(`Record a completed overhaul for ${e.engine_id}? Hours since overhaul will reset to 0.`) && run(e.engine_id, () => api(`/engines/${e.engine_id}/overhaul`, { method: "POST" }), reload)}>Record overhaul</Button> : <span className="text-xs text-slate-400">Read-only</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
