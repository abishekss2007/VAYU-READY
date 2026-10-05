"use client";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, Stat, TableWrap, useLoad } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { canSee } from "@/lib/nav";
import { useAction, useSession } from "@/lib/session";

function Countdown({ row }: { row: any }) {
  if (row.reported_at) return <Badge tone="green">Reported {fmtTime(row.reported_at)}</Badge>;
  return <Badge tone={row.overdue ? "red" : row.hours_left < 2 ? "amber" : "blue"}>{row.overdue ? `Overdue by ${Math.abs(row.hours_left).toFixed(1)} h` : `${row.hours_left.toFixed(1)} h left to report`}</Badge>;
}

export default function Compliance() {
  const { me, tick } = useSession();
  const admin = me?.role === "ADMIN";
  const c = useLoad(() => api("/compliance"), [tick]);
  const inc = useLoad(() => api("/incidents"), [tick]);
  const br = useLoad(() => api("/breaches"), [tick]);
  const { busy, run } = useAction();
  const [itype, setItype] = useState("");
  const [idesc, setIdesc] = useState("");
  const [b, setB] = useState({ what_happened: "", impact: "", steps_taken: "", affected: "" });

  if (c.loading && !c.data) return <Loading label="Loading compliance checklist..." />;
  if (c.error) return <ErrorBox>{c.error}</ErrorBox>;
  const d = c.data;
  return (
    <div>
      <PageTitle title="Compliance" question="Which rules does the system meet, and what is still to do before real deployment?" />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Checklist items done" value={d.summary.done} tone="green" />
        <Stat label="Checklist items pending" value={d.summary.pending} tone={d.summary.pending ? "amber" : "green"} sub="deployment steps on the base server" />
        <Stat label="Open cyber incidents" value={(inc.data?.incidents || []).filter((i: any) => !i.reported_at).length} sub="6-hour CERT-In clock" />
        <Stat label="Open data breaches" value={(br.data || []).filter((x: any) => !x.reported_at).length} sub="72-hour DPDP clock" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {d.groups.map((g: any) => (
          <Card key={g.group}>
            <CardHeader title={g.group} />
            <ul className="divide-y divide-slate-100">
              {g.items.map((i: any) => (
                <li key={i.item} className="flex items-start justify-between gap-3 px-4 py-2.5 text-sm">
                  <div className="min-w-0"><div className="font-medium text-slate-800">{i.item}</div><div className="text-xs text-slate-500">{i.how}</div></div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Badge tone={i.status === "Done" ? "green" : "amber"}>{i.status}</Badge>
                    {me && canSee(me.role, i.link) && i.link !== "/compliance" && <Link href={i.link} className="text-xs text-sky-700 hover:underline">Open feature</Link>}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))}

        <Card>
          <CardHeader title="ISO 13374 layer mapping" sub="Each backend module is labelled with its condition-monitoring block" />
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Block</th><th className="th">Modules</th></tr></thead>
            <tbody>{d.iso_13374.map((r: any, i: number) => <tr key={r.block} className="border-b border-slate-100"><td className="td whitespace-nowrap font-medium">{i + 1}. {r.block}</td><td className="td text-xs">{r.modules.join("; ")}</td></tr>)}</tbody>
          </TableWrap>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Report cyber incident (CERT-In)" sub={`Report to ${inc.data?.report_to || "incident@cert-in.org.in"} within 6 hours of noticing. This system is offline: send the report through an approved channel. Point of Contact: ${d.settings.certin_poc_name || "not set"}.`} />
          <div className="space-y-3 p-4">
            {(admin || me?.role === "CO") && (
              <div className="space-y-2">
                <div><label className="label" htmlFor="itype">Incident type (CERT-In Directions 2022)</label>
                  <select id="itype" className="input" value={itype} onChange={(e) => setItype(e.target.value)}><option value="">Choose type</option>{(inc.data?.types || []).map((t: string) => <option key={t}>{t}</option>)}</select></div>
                <div><label className="label" htmlFor="idesc">What happened</label><textarea id="idesc" className="input" rows={2} value={idesc} onChange={(e) => setIdesc(e.target.value)} /></div>
                <Button size="sm" variant="danger" busy={busy === "inc"} disabled={!itype || idesc.trim().length < 5} onClick={() => run("inc", () => api("/incidents", { body: { incident_type: itype, description: idesc } }), () => { setItype(""); setIdesc(""); inc.reload(); })}>Record incident and start 6-hour clock</Button>
              </div>
            )}
            {inc.loading && !inc.data ? <Loading /> : !inc.data?.incidents?.length ? <Empty>No cyber incidents recorded.</Empty> : (
              <ul className="divide-y divide-slate-100 text-sm">
                {inc.data.incidents.map((i: any) => (
                  <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div className="min-w-0"><div className="font-medium">#{i.id} {i.incident_type}</div><div className="text-xs text-slate-500">{i.description} · noticed {fmtTime(i.noticed_at)}</div></div>
                    <div className="flex items-center gap-2"><Countdown row={i} />{admin && !i.reported_at && <Button size="sm" variant="outline" busy={busy === `i${i.id}`} onClick={() => run(`i${i.id}`, () => api(`/incidents/${i.id}/reported`, { method: "POST" }), inc.reload)}>Mark reported</Button>}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Personal-data breach (DPDP Act 2023)" sub="Records what happened, the impact and steps taken; informs affected users; report to the Data Protection Board within 72 hours." />
          <div className="space-y-3 p-4">
            {admin && (
              <div className="space-y-2">
                <div><label className="label" htmlFor="bw">What happened</label><textarea id="bw" className="input" rows={2} value={b.what_happened} onChange={(e) => setB({ ...b, what_happened: e.target.value })} /></div>
                <div className="grid grid-cols-2 gap-2">
                  <div><label className="label" htmlFor="bi">Impact</label><input id="bi" className="input" value={b.impact} onChange={(e) => setB({ ...b, impact: e.target.value })} /></div>
                  <div><label className="label" htmlFor="bs">Steps taken</label><input id="bs" className="input" value={b.steps_taken} onChange={(e) => setB({ ...b, steps_taken: e.target.value })} /></div>
                </div>
                <div><label className="label" htmlFor="ba">Affected users (emails, comma separated)</label><input id="ba" className="input" value={b.affected} onChange={(e) => setB({ ...b, affected: e.target.value })} placeholder="tech@vayu.demo" /></div>
                <Button size="sm" variant="danger" busy={busy === "br"} disabled={b.what_happened.trim().length < 5 || b.impact.trim().length < 3 || b.steps_taken.trim().length < 3}
                  onClick={() => run("br", () => api("/breaches", { body: { what_happened: b.what_happened, impact: b.impact, steps_taken: b.steps_taken, affected_users: b.affected.split(",").map((x) => x.trim()).filter(Boolean) } }), () => { setB({ what_happened: "", impact: "", steps_taken: "", affected: "" }); br.reload(); })}>Record breach and start 72-hour clock</Button>
              </div>
            )}
            {br.loading && !br.data ? <Loading /> : !br.data?.length ? <Empty>No personal-data breaches recorded.</Empty> : (
              <ul className="divide-y divide-slate-100 text-sm">
                {br.data.map((x: any) => (
                  <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div className="min-w-0"><div className="font-medium">#{x.id} {x.what_happened}</div><div className="text-xs text-slate-500">Impact: {x.impact} · Steps: {x.steps_taken} · {x.affected_users.length} user(s) informed</div></div>
                    <div className="flex items-center gap-2"><Countdown row={x} />{admin && !x.reported_at && <Button size="sm" variant="outline" busy={busy === `b${x.id}`} onClick={() => run(`b${x.id}`, () => api(`/breaches/${x.id}/reported`, { method: "POST" }), br.reload)}>Mark reported</Button>}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
