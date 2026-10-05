"use client";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, useLoad } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

export default function Privacy() {
  const { me, tick } = useSession();
  const admin = me?.role === "ADMIN";
  const profile = useLoad(() => api("/me/profile"), [tick]);
  const notice = useLoad(() => api("/me/notice"), []);
  const g = useLoad(() => api("/grievances"), [tick]);
  const breaches = useLoad(() => api("/me/breach-notices"), [tick]);
  const { busy, run } = useAction();
  const [kind, setKind] = useState("Grievance");
  const [text, setText] = useState("");
  const [reply, setReply] = useState<Record<number, string>>({});

  return (
    <div>
      <PageTitle title="My Data & Privacy" question="What personal data does the system hold about me, and how do I get it corrected?" />
      {(breaches.data || []).map((b: any) => (
        <div key={b.id} className="mb-3 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
          <b>Data breach notice ({fmtTime(b.detected_at)}):</b> {b.what_happened} Impact: {b.impact} Steps taken: {b.steps_taken}
        </div>
      ))}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="My data" sub="Only what is needed is stored" />
          {profile.error ? <div className="p-3"><ErrorBox>{profile.error}</ErrorBox></div> : profile.loading && !profile.data ? <Loading /> : profile.data && (
            <div className="space-y-2 p-4 text-sm">
              {Object.entries(profile.data.personal_data_held).map(([k, v]) => <div key={k} className="flex justify-between border-b border-slate-100 py-1"><span className="capitalize text-slate-500">{k}</span><span className="font-medium">{(v as string) || "All squadrons"}</span></div>)}
              <p className="text-xs text-slate-500">Purpose: {profile.data.purpose}. Not stored: {profile.data.not_stored.join(", ")}.</p>
              <p className="text-xs text-slate-500">{profile.data.how_to_correct}</p>
            </div>
          )}
        </Card>
        <Card>
          <CardHeader title="Privacy notice / गोपनीयता सूचना" />
          {notice.loading && !notice.data ? <Loading /> : notice.data && (
            <div className="space-y-3 p-4 text-sm text-slate-700"><p>{notice.data.en.body}</p><p lang="hi">{notice.data.hi.body}</p></div>
          )}
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title={admin ? "Grievances and correction requests (all users)" : "Grievance or correction request"} sub="Every request gets a tracked response from the Admin" />
        <div className="space-y-3 p-4">
          {!admin && (
            <div className="grid gap-2 md:grid-cols-[10rem_1fr_auto] md:items-end">
              <div><label className="label" htmlFor="gk">Type</label><select id="gk" className="input" value={kind} onChange={(e) => setKind(e.target.value)}><option value="Grievance">Grievance</option><option value="Correction">Correction of my data</option></select></div>
              <div><label className="label" htmlFor="gt">Your request</label><input id="gt" className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. My name is spelt wrongly" /></div>
              <Button busy={busy === "g"} disabled={text.trim().length < 5} onClick={() => run("g", () => api("/grievances", { body: { kind, text } }), () => { setText(""); g.reload(); })}>Send</Button>
            </div>
          )}
          {g.error ? <ErrorBox>{g.error}</ErrorBox> : g.loading && !g.data ? <Loading /> : !g.data?.length ? <Empty>No requests yet.</Empty> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {g.data.map((x: any) => (
                <li key={x.id} className="py-2">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={x.status === "Resolved" ? "green" : "amber"}>{x.status}</Badge><span className="font-medium">#{x.id} {x.kind}</span><span className="text-xs text-slate-500">{x.raised_by} · {fmtTime(x.created_at)}</span></div>
                  <div>{x.text}</div>
                  {x.response && <div className="mt-1 rounded bg-slate-50 p-2 text-xs">Response from {x.responded_by} ({fmtTime(x.responded_at)}): {x.response}</div>}
                  {admin && x.status === "Open" && (
                    <div className="mt-2 flex gap-2">
                      <input className="input" aria-label={`Response to request ${x.id}`} placeholder="Your response" value={reply[x.id] || ""} onChange={(e) => setReply({ ...reply, [x.id]: e.target.value })} />
                      <Button size="sm" busy={busy === `r${x.id}`} disabled={(reply[x.id] || "").trim().length < 3} onClick={() => run(`r${x.id}`, () => api(`/grievances/${x.id}/respond`, { body: { response: reply[x.id] } }), g.reload)}>Respond</Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
