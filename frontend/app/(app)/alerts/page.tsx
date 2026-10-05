"use client";
import Link from "next/link";
import { useState } from "react";
import { ReviewDialog } from "@/components/review-dialog";
import { Advisory, Badge, Button, Card, Empty, ErrorBox, Loading, PageTitle, severityTone, TableWrap, useLoad } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { useSession } from "@/lib/session";

const DECISION: Record<string, string> = { Inspect: "Inspect", Schedule: "Schedule engine change", FalseAlarm: "False alarm" };

export default function Alerts() {
  const { me, tick } = useSession();
  const { data, error, loading, reload } = useLoad(() => api("/alerts"), [tick]);
  const [review, setReview] = useState<any>(null);
  const [showAll, setShowAll] = useState(false);
  const rows = (data?.alerts || []).filter((a: any) => showAll || !a.reviewed_at);
  return (
    <div>
      <PageTitle title="Alerts" question="What needs a decision? Critical alerts must be reviewed by an Engineering Officer within 12 hours."
        right={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />Show reviewed alerts</label>} />
      {error && <ErrorBox>{error}</ErrorBox>}
      <Card>
        {loading && !data ? <Loading /> : rows.length === 0 ? <Empty>No open alerts. Tick “Show reviewed alerts” to see history.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Alert</th><th className="th">Aircraft</th><th className="th">What</th><th className="th">Raised</th><th className="th">Review</th><th className="th">Action</th></tr></thead>
            <tbody>
              {rows.map((a: any) => (
                <tr key={a.id} className="border-b border-slate-100">
                  <td className="td whitespace-nowrap"><Badge tone={severityTone(a.severity)}>{a.severity}</Badge><div className="mt-1 text-xs text-slate-500">{a.id} · {a.kind}</div></td>
                  <td className="td font-medium"><Link className="text-sky-700 hover:underline" href={`/aircraft/${a.tail_no}`}>{a.tail_no}</Link></td>
                  <td className="td">{a.message}{a.note && <div className="text-xs text-slate-500">Note: {a.note}</div>}</td>
                  <td className="td whitespace-nowrap text-xs">{fmtTime(a.created_at)}</td>
                  <td className="td text-xs">
                    {a.reviewed_at ? <><Badge tone="green">{DECISION[a.decision] || "Reviewed"}</Badge><div className="mt-1 text-slate-500">{a.reviewed_by}</div></>
                      : a.hours_left != null ? <Badge tone={a.overdue ? "red" : "amber"}>{a.overdue ? `Overdue by ${Math.abs(a.hours_left).toFixed(0)} h` : `${a.hours_left.toFixed(0)} h left`}</Badge>
                      : <span className="text-slate-500">Not reviewed</span>}
                    {a.escalated && <div className="mt-1"><Badge tone="red">Escalated to Commander</Badge></div>}
                  </td>
                  <td className="td whitespace-nowrap">
                    {!a.reviewed_at && me?.role === "ENGO" ? <Button size="sm" onClick={() => setReview(a)}>Review alert</Button>
                      : <Link href={a.action_link} className="inline-flex min-h-[32px] items-center rounded-md border border-slate-300 px-2.5 text-xs font-medium hover:bg-slate-50">{a.reviewed_at ? "Open aircraft" : a.action_label === "Review alert" ? "Open aircraft" : a.action_label}</Link>}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
      <div className="mt-3"><Advisory /></div>
      {review && <ReviewDialog alert={review} onClose={() => setReview(null)} onDone={() => { setReview(null); reload(); }} />}
    </div>
  );
}
