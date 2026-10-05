"use client";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, TableWrap, useLoad } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

export default function Spares() {
  const { me, tick } = useSession();
  const logo = me?.role === "LOGO";
  const parts = useLoad(() => api("/parts"), [tick]);
  const indents = useLoad(() => api("/indents"), [tick]);
  const { busy, run } = useAction();
  const reload = () => { parts.reload(); indents.reload(); };
  const low = (parts.data || []).filter((p: any) => p.below_reorder);

  return (
    <div>
      <PageTitle title="Spares and Indents" question="Which parts will ground an aircraft, and are they on order in time?" />

      <Card className="mb-4">
        <CardHeader title="Indents" sub="Sorted by “needed by” date. Indents raised by “system” were raised automatically from a predicted failure or low stock." />
        {indents.error ? <div className="p-3"><ErrorBox>{indents.error}</ErrorBox></div> : indents.loading && !indents.data ? <Loading /> : !indents.data?.length ? <Empty>No indents.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Indent</th><th className="th">Part</th><th className="th">For aircraft</th><th className="th">Timing</th><th className="th">Status</th><th className="th">Action</th></tr></thead>
            <tbody>
              {indents.data.map((i: any) => (
                <tr key={i.id} className={`border-b border-slate-100 ${i.late ? "bg-red-50/60" : ""}`}>
                  <td className="td whitespace-nowrap font-medium">{i.id}<div className="text-xs font-normal text-slate-500">raised by {i.raised_by}</div></td>
                  <td className="td">{i.part_name} <span className="text-xs text-slate-500">({i.part_no}) × {i.qty}</span><div className="text-xs text-slate-500">{i.reason}</div></td>
                  <td className="td whitespace-nowrap">{i.tail_no || "Stock"}</td>
                  <td className={`td min-w-[12rem] text-xs ${i.late ? "font-medium text-crit" : ""}`}>
                    {i.status === "Received" ? "Received" : <>{i.stock} in stock, lead time {i.lead_time_days} days, needed in {i.needed_in_days} days<div>{i.late ? `Arrives in ${i.arrives_in_days} days: too late` : `Arrives in ${i.arrives_in_days} days`}</div></>}
                    <div className="text-slate-500">Needed by {fmtDate(i.needed_by)}</div>
                  </td>
                  <td className="td"><Badge tone={i.status === "Received" ? "green" : i.status === "Approved" ? "blue" : "amber"}>{i.status}</Badge></td>
                  <td className="td whitespace-nowrap">
                    {logo && i.status === "Raised" && <Button size="sm" busy={busy === i.id} onClick={() => run(i.id, () => api(`/indents/${i.id}/approve`, { method: "POST" }), reload)}>Approve</Button>}
                    {logo && i.status === "Approved" && <Button size="sm" variant="success" busy={busy === i.id} onClick={() => run(i.id, () => api(`/indents/${i.id}/receive`, { method: "POST" }), reload)}>Mark received</Button>}
                    {(!logo || i.status === "Received") && <span className="text-xs text-slate-400">{i.status === "Received" ? (i.fitted ? "Fitted" : "Awaiting ENGO release") : "Logistics Officer acts"}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>

      <Card>
        <CardHeader title="Stock" sub={`${low.length} part${low.length === 1 ? "" : "s"} below reorder point. Demand = parts needed in the next 30 days by AOG aircraft and predicted failures.`} />
        {parts.error ? <div className="p-3"><ErrorBox>{parts.error}</ErrorBox></div> : parts.loading && !parts.data ? <Loading /> : !parts.data?.length ? <Empty>No parts.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Part</th><th className="th">System</th><th className="th">In stock</th><th className="th">Reorder point</th><th className="th">Lead time</th><th className="th">Demand (30 days)</th><th className="th">On order</th><th className="th">Stock level</th></tr></thead>
            <tbody>
              {parts.data.map((p: any) => (
                <tr key={p.part_no} className="border-b border-slate-100">
                  <td className="td font-medium">{p.name}<div className="text-xs font-normal text-slate-500">{p.part_no}</div></td>
                  <td className="td">{p.system}</td>
                  <td className={`td font-semibold ${p.below_reorder ? "text-crit" : ""}`}>{p.stock}</td>
                  <td className="td">{p.reorder_point}</td>
                  <td className="td">{p.lead_time_days} days</td>
                  <td className="td">{p.demand_30_days}{p.shortfall > 0 && <span className="ml-1 text-xs text-crit">(short by {p.shortfall})</span>}</td>
                  <td className="td">{p.on_order}</td>
                  <td className="td"><Badge tone={p.below_reorder ? "red" : "green"}>{p.below_reorder ? "Below reorder point" : "OK"}</Badge></td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}
