"use client";
import { useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, Modal, PageTitle, TableWrap, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { ROLE_NAME, Role } from "@/lib/nav";
import { useAction, useSession } from "@/lib/session";

const ROLES = Object.keys(ROLE_NAME) as Role[];

export default function Admin() {
  const { tick } = useSession();
  const users = useLoad(() => api("/users"), [tick]);
  const bases = useLoad(() => api("/bases"), [tick]);
  const aircraft = useLoad(() => api("/aircraft?include_archived=true"), [tick]);
  const stream = useLoad(() => api("/stream/status"), [tick]);
  const cfg = useLoad(() => api("/settings"), [tick]);
  const { busy, run } = useAction();
  const [addUser, setAddUser] = useState(false);
  const [addAc, setAddAc] = useState(false);
  const [importRes, setImportRes] = useState<any>(null);
  const file = useRef<HTMLInputElement>(null);
  const squadrons = bases.data?.squadrons || [];

  const upload = () => {
    const f = file.current?.files?.[0];
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    run("import", () => api("/import/records", { form }), (r) => { setImportRes(r); aircraft.reload(); });
  };

  return (
    <div>
      <PageTitle title="Users & Access" question="Who can use the system, and which aircraft and bases are on record? Admin has no access to maintenance decisions."
        right={<Button variant="danger" size="sm" busy={busy === "reset"} onClick={() => confirm("Reload the demo data? All changes made during the demo are replaced and the score returns to 71.") && run("reset", () => api("/demo/reset", { method: "POST" }), () => location.reload())}>Reset demo</Button>} />

      <Card className="mb-4">
        <CardHeader title="Users" sub="2-step login is required for CO, ENGO, LOGO, Auditor and Admin. Accounts lock after 5 failed logins." right={<Button size="sm" onClick={() => setAddUser(true)}>Add user</Button>} />
        {users.error ? <div className="p-3"><ErrorBox>{users.error}</ErrorBox></div> : users.loading && !users.data ? <Loading /> : !users.data?.length ? <Empty>No users.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th">Squadron</th><th className="th">2-step</th><th className="th">State</th><th className="th">Action</th></tr></thead>
            <tbody>
              {users.data.map((u: any) => (
                <tr key={u.id} className="border-b border-slate-100">
                  <td className="td font-medium">{u.name}</td><td className="td text-xs">{u.email}</td><td className="td"><Badge>{ROLE_NAME[u.role as Role]}</Badge></td>
                  <td className="td">{u.squadron_code || "All"}</td><td className="td">{u.otp_required ? "Yes" : "No"}</td>
                  <td className="td"><Badge tone={!u.active ? "grey" : u.locked ? "red" : "green"}>{!u.active ? "Inactive" : u.locked ? "Locked" : "Active"}</Badge></td>
                  <td className="td whitespace-nowrap">
                    {u.locked && <Button size="sm" variant="outline" busy={busy === `u${u.id}`} onClick={() => run(`u${u.id}`, () => api(`/users/${u.id}`, { method: "PATCH", body: { unlock: true } }), users.reload)}>Unlock</Button>}{" "}
                    <Button size="sm" variant="outline" busy={busy === `a${u.id}`} onClick={() => run(`a${u.id}`, () => api(`/users/${u.id}`, { method: "PATCH", body: { active: !u.active } }), users.reload)}>{u.active ? "Deactivate" : "Activate"}</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Bases and squadrons" />
          {bases.loading && !bases.data ? <Loading /> : !bases.data?.bases?.length ? <Empty>No bases.</Empty> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {bases.data.bases.map((b: any) => (
                <li key={b.code} className="px-4 py-2"><span className="font-medium">{b.name}</span> <span className="text-xs text-slate-500">({b.code})</span>
                  <div className="text-xs text-slate-500">{squadrons.filter((s: any) => s.base_code === b.code).map((s: any) => `${s.name} (${s.code}), target ${s.availability_target * 100}%`).join("; ") || "No squadrons"}</div></li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Live sensor feed (MQTT replay)" sub="Replays stored sensor cycles as a live feed for the dashboards" />
          {stream.loading && !stream.data ? <Loading /> : stream.data && (
            <div className="space-y-2 p-4 text-sm">
              <div>Replay: <Badge tone={stream.data.running ? "green" : "grey"}>{stream.data.running ? "Running" : "Stopped"}</Badge> · Broker: <Badge tone={stream.data.broker_connected ? "green" : "amber"}>{stream.data.broker_connected ? "Connected" : "Not connected"}</Badge></div>
              <div className="text-xs text-slate-500">Messages received: {stream.data.messages_received} · Dashboards connected: {stream.data.dashboards_connected}</div>
              <div className="flex gap-2">
                <Button size="sm" variant="success" busy={busy === "start"} disabled={stream.data.running} onClick={() => run("start", () => api("/stream/start", { method: "POST" }), stream.reload)}>Start replay</Button>
                <Button size="sm" variant="outline" busy={busy === "stop"} disabled={!stream.data.running} onClick={() => run("stop", () => api("/stream/stop", { method: "POST" }), stream.reload)}>Stop replay</Button>
              </div>
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Aircraft records" sub="Records are never deleted, only archived with a reason. A new record starts as “In maintenance” until an Engineering Officer releases it." right={<Button size="sm" onClick={() => setAddAc(true)}>Add aircraft</Button>} />
        {aircraft.loading && !aircraft.data ? <Loading /> : !aircraft.data?.length ? <Empty>No aircraft records.</Empty> : (
          <div className="max-h-80 overflow-y-auto"><TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">Tail number</th><th className="th">Type</th><th className="th">Squadron</th><th className="th">Flying hours</th><th className="th">Record</th><th className="th">Action</th></tr></thead>
            <tbody>
              {[...aircraft.data].sort((a: any, b: any) => a.tail_no.localeCompare(b.tail_no)).map((a: any) => (
                <tr key={a.tail_no} className="border-b border-slate-100">
                  <td className="td font-medium">{a.tail_no}</td><td className="td">{a.type}</td><td className="td">{a.squadron_code}</td><td className="td">{a.flying_hours} h</td>
                  <td className="td"><Badge tone={a.archived ? "grey" : "green"}>{a.archived ? "Archived" : "Active"}</Badge>{a.archived_reason && <div className="text-xs text-slate-500">{a.archived_reason}</div>}</td>
                  <td className="td">{!a.archived ? <Button size="sm" variant="outline" busy={busy === a.tail_no} onClick={() => { const reason = prompt(`Reason for archiving ${a.tail_no}:`); if (reason) run(a.tail_no, () => api(`/aircraft/${a.tail_no}`, { method: "PATCH", body: { archived: true, archived_reason: reason } }), aircraft.reload); }}>Archive</Button>
                    : <Button size="sm" variant="outline" busy={busy === a.tail_no} onClick={() => run(a.tail_no, () => api(`/aircraft/${a.tail_no}`, { method: "PATCH", body: { archived: false } }), aircraft.reload)}>Restore</Button>}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap></div>
        )}
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Bulk import of technical records" sub="CSV or Excel with columns: tail_no, flying_hours, engine_position, hours_since_overhaul" />
          <div className="space-y-3 p-4 text-sm">
            <input ref={file} type="file" accept=".csv,.xlsx" className="block w-full text-sm" aria-label="Technical records file" />
            <Button size="sm" busy={busy === "import"} onClick={upload}>Upload and check</Button>
            {importRes && (
              <div>
                <div className="font-medium">{importRes.saved} row(s) saved, {importRes.rejected} row(s) rejected.</div>
                <ul className="mt-1 space-y-0.5 text-xs text-crit">{importRes.errors.map((e: any) => <li key={e.row}>{e.message}</li>)}</ul>
              </div>
            )}
          </div>
        </Card>
        <SettingsCard cfg={cfg} />
      </div>

      {addUser && <AddUser squadrons={squadrons} onClose={() => setAddUser(false)} onDone={() => { setAddUser(false); users.reload(); }} />}
      {addAc && <AddAircraft squadrons={squadrons} onClose={() => setAddAc(false)} onDone={() => { setAddAc(false); aircraft.reload(); }} />}
    </div>
  );
}

function SettingsCard({ cfg }: { cfg: any }) {
  const [form, setForm] = useState<any>(null);
  const { busy, run } = useAction();
  const v = form || cfg.data;
  const field = (key: string, label: string) => (
    <div><label className="label" htmlFor={key}>{label}</label>
      <input id={key} className="input" value={v?.[key] || ""} onChange={(e) => setForm({ ...v, [key]: e.target.value })} /></div>
  );
  return (
    <Card>
      <CardHeader title="Deployment settings" sub="Classification banner, CERT-In Point of Contact, NTP servers" />
      {cfg.loading && !cfg.data ? <Loading /> : (
        <div className="space-y-3 p-4">
          {field("classification", "Classification banner (shown on every page and export)")}
          {field("certin_poc_name", "CERT-In Point of Contact: name")}
          {field("certin_poc_contact", "CERT-In Point of Contact: contact")}
          {field("ntp_servers", "NTP servers (NIC / NPL)")}
          {field("grievance_contact", "Privacy and grievance contact")}
          <Button size="sm" busy={busy === "cfg"} disabled={!form} onClick={() => run("cfg", () => api("/settings", { method: "PUT", body: { classification: form.classification, certin_poc_name: form.certin_poc_name, certin_poc_contact: form.certin_poc_contact, ntp_servers: form.ntp_servers, grievance_contact: form.grievance_contact } }), () => { setForm(null); cfg.reload(); })}>Save settings</Button>
        </div>
      )}
    </Card>
  );
}

function AddUser({ squadrons, onClose, onDone }: any) {
  const [f, setF] = useState({ name: "", email: "", role: "TECH", squadron_code: "", password: "" });
  const { busy, run } = useAction();
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal title="Add user" onClose={onClose}>
      <div className="space-y-3">
        <p className="text-xs text-slate-500">Only name, role, squadron and email are stored (data minimisation).</p>
        <div><label className="label" htmlFor="un">Name</label><input id="un" className="input" value={f.name} onChange={set("name")} /></div>
        <div><label className="label" htmlFor="ue">Email</label><input id="ue" className="input" type="email" value={f.email} onChange={set("email")} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label" htmlFor="ur">Role</label><select id="ur" className="input" value={f.role} onChange={set("role")}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_NAME[r]}</option>)}</select></div>
          <div><label className="label" htmlFor="us">Squadron</label><select id="us" className="input" value={f.squadron_code} onChange={set("squadron_code")}><option value="">All / none</option>{squadrons.map((s: any) => <option key={s.code} value={s.code}>{s.code}</option>)}</select></div>
        </div>
        <div><label className="label" htmlFor="up">Temporary password (6+ characters)</label><input id="up" className="input" type="password" value={f.password} onChange={set("password")} /></div>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button busy={busy === "add"} onClick={() => run("add", () => api("/users", { body: { ...f, squadron_code: f.squadron_code || null } }), onDone)}>Add user</Button></div>
      </div>
    </Modal>
  );
}

function AddAircraft({ squadrons, onClose, onDone }: any) {
  const [f, setF] = useState({ tail_no: "TAIL-SQ7-119", type: "Demo Fighter-A", squadron_code: "SQ7", flying_hours: "0" });
  const { busy, run } = useAction();
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal title="Add aircraft record" onClose={onClose}>
      <div className="space-y-3">
        <div><label className="label" htmlFor="at">Tail number (format TAIL-SQ7-119)</label><input id="at" className="input" value={f.tail_no} onChange={set("tail_no")} /></div>
        <div><label className="label" htmlFor="ay">Type</label><input id="ay" className="input" value={f.type} onChange={set("type")} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label" htmlFor="as">Squadron</label><select id="as" className="input" value={f.squadron_code} onChange={set("squadron_code")}>{squadrons.map((s: any) => <option key={s.code} value={s.code}>{s.code}</option>)}</select></div>
          <div><label className="label" htmlFor="ah">Flying hours</label><input id="ah" className="input" type="number" min="0" value={f.flying_hours} onChange={set("flying_hours")} /></div>
        </div>
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button busy={busy === "add"} onClick={() => run("add", () => api("/aircraft", { body: { ...f, flying_hours: Number(f.flying_hours) || 0 } }), onDone)}>Add aircraft</Button></div>
      </div>
    </Modal>
  );
}
