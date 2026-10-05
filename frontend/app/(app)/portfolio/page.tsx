"use client";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, CardHeader, cn, Empty, ErrorBox, Loading, PageTitle, TableWrap, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function Portfolio() {
  const { tick } = useSession();
  const { data, error, loading } = useLoad(() => api("/portfolio"), [tick]);
  if (loading && !data) return <Loading label="Loading portfolio..." />;
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return null;
  return (
    <div>
      <PageTitle title="Portfolio · all squadrons" question="Which squadrons are ready, and what is grounding aircraft across bases?" />
      <div className="grid gap-4 md:grid-cols-2">
        {data.squadrons.map((s: any) => (
          <Card key={s.code}>
            <CardHeader title={`${s.name} · ${s.base}`} right={<Link href="/dashboard" className="text-xs text-sky-700 hover:underline">Open dashboard</Link>} />
            <div className="flex items-center gap-5 p-4">
              <div className="text-center"><div className={cn("text-5xl font-bold", s.score >= 80 ? "text-ok" : s.score >= 60 ? "text-warn" : "text-crit")}>{s.score}</div><div className="text-xs text-slate-500">Fleet Health Score</div></div>
              <div className="flex-1 space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Availability today</span><span className="font-medium">{s.kpis.mission_capable}/{s.kpis.total} ({(s.availability * 100).toFixed(0)}%)</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Forecast in {s.kpis.forecast_day} days</span><span className="font-medium">{s.kpis.forecast_mission_capable}/{s.kpis.total}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">AOG awaiting spares</span><span className="font-medium">{s.kpis.aog_awaiting_spares}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Critical alerts</span><span className="font-medium">{s.kpis.critical_alerts}</span></div>
              </div>
            </div>
            <ul className="border-t border-slate-100 px-4 py-2 text-xs text-slate-600">
              {s.rules.filter((r: any) => r.points < 0).map((r: any) => <li key={r.key} className="flex justify-between py-0.5"><span>{r.label}: {r.detail}</span><span className="font-medium text-crit">{r.points}</span></li>)}
              {s.rules.every((r: any) => r.points === 0) && <li>No points lost.</li>}
            </ul>
          </Card>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Top AOG causes" sub="Aircraft on ground, by cause, across all squadrons" />
          {data.top_aog_causes.length === 0 ? <Empty>No aircraft on ground.</Empty> : (
            <div className="h-56 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top_aog_causes} layout="vertical" margin={{ left: 40, right: 16 }}>
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="cause" tick={{ fontSize: 11 }} width={110} />
                  <Tooltip formatter={(v: any) => [`${v} aircraft`, "On ground"]} />
                  <Bar dataKey="aircraft" fill="#0ea5e9" isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Spares causing the most groundings" />
          {data.top_grounding_spares.length === 0 ? <Empty>No aircraft is waiting for a part.</Empty> : (
            <TableWrap>
              <thead><tr className="border-b border-slate-200"><th className="th">Part</th><th className="th">Aircraft grounded</th><th className="th">In stock</th><th className="th">Lead time</th></tr></thead>
              <tbody>{data.top_grounding_spares.map((p: any) => (
                <tr key={p.part_no} className="border-b border-slate-100"><td className="td font-medium">{p.name}<div className="text-xs font-normal text-slate-500">{p.part_no}</div></td>
                  <td className="td"><Badge tone="red">{p.aircraft_grounded}</Badge></td><td className="td">{p.stock}</td><td className="td">{p.lead_time_days} days</td></tr>
              ))}</tbody>
            </TableWrap>
          )}
        </Card>
      </div>
    </div>
  );
}
