"use client";
import Link from "next/link";
import { useState } from "react";
import { Badge, Card, Empty, ErrorBox, healthTone, Loading, PageTitle, statusTone, TableWrap, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function AircraftHealth() {
  const { tick } = useSession();
  const [status, setStatus] = useState("");
  const { data, error, loading } = useLoad(() => api(`/aircraft${status ? `?status=${status}` : ""}`), [tick, status]);
  return (
    <div>
      <PageTitle title="Aircraft Health" question="Which aircraft need attention first? Sorted by lowest health score."
        right={<select className="input w-auto" aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="MC">Mission-capable</option><option value="PMC">Partially capable</option>
          <option value="AOG">AOG</option><option value="MAINT">In maintenance</option>
        </select>} />
      {error && <ErrorBox>{error}</ErrorBox>}
      <Card>
        {loading && !data ? <Loading /> : !data?.length ? <Empty>No aircraft match this filter.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200">
              <th className="th">Tail number</th><th className="th">Health (0–100)</th><th className="th">Lowest engine RUL</th>
              <th className="th">Status</th><th className="th">Mission readiness</th><th className="th">Flying hours</th><th className="th">Action</th>
            </tr></thead>
            <tbody>
              {data.map((a: any) => (
                <tr key={a.tail_no} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="td font-medium"><Link className="text-sky-700 hover:underline" href={`/aircraft/${a.tail_no}`}>{a.tail_no}</Link><div className="text-xs text-slate-500">{a.type} · {a.squadron_code}</div></td>
                  <td className="td"><Badge tone={healthTone(a.health_score)}>{a.health_score}</Badge></td>
                  <td className="td">{a.min_rul_cycles != null ? <span className={a.min_rul_cycles < 25 ? "font-semibold text-crit" : ""}>{a.min_rul_cycles.toFixed(0)} cycles</span> : "-"}</td>
                  <td className="td"><Badge tone={statusTone(a.status)}>{a.status_label}</Badge></td>
                  <td className="td">{a.readiness}</td>
                  <td className="td">{a.flying_hours.toLocaleString()} h</td>
                  <td className="td"><Link href={`/aircraft/${a.tail_no}`} className="inline-flex min-h-[32px] items-center rounded-md border border-slate-300 px-2.5 text-xs font-medium hover:bg-slate-50">Open twin</Link></td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}
