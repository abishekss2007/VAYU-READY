"use client";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Empty, ErrorBox, Loading, PageTitle, TableWrap, useLoad } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { useAction, useSession } from "@/lib/session";

export default function Audit() {
  const { tick } = useSession();
  const { data, error, loading } = useLoad(() => api("/audit"), [tick]);
  const [result, setResult] = useState<any>(null);
  const { busy, run } = useAction();
  return (
    <div>
      <PageTitle title="Audit Trail" question="Who did what, and has anything been changed afterwards?"
        right={<Button busy={busy === "verify"} onClick={() => run("verify", () => api("/audit/verify").then((r) => ({ ...r, message: undefined, result: r })), (r) => setResult(r.result))}>Verify chain</Button>} />
      {result && (
        <div className={`mb-4 flex items-center gap-3 rounded-lg border px-4 py-3 ${result.intact ? "border-green-200 bg-green-50 text-green-800" : "border-red-200 bg-red-50 text-red-800"}`} role="status">
          {result.intact ? <ShieldCheck className="h-6 w-6" /> : <ShieldAlert className="h-6 w-6" />}
          <div>
            <div className="font-semibold">{result.intact ? "All entries intact" : `Tampering found at entry ${result.first_broken_entry}`}</div>
            <div className="text-xs">{result.intact ? `${result.entries} entries checked: every SHA-256 hash matches.` : result.message}</div>
          </div>
        </div>
      )}
      {error && <ErrorBox>{error}</ErrorBox>}
      <Card>
        <CardHeader title="Entries" sub="Append-only. Each entry is SHA-256 hash-chained to the one before it; the database blocks UPDATE and DELETE." />
        {loading && !data ? <Loading /> : !data?.length ? <Empty>No audit entries yet.</Empty> : (
          <TableWrap>
            <thead><tr className="border-b border-slate-200"><th className="th">No.</th><th className="th">Time</th><th className="th">Person</th><th className="th">Role</th><th className="th">Action</th><th className="th">Detail</th><th className="th">Hash</th></tr></thead>
            <tbody>
              {data.map((e: any) => (
                <tr key={e.id} className={`border-b border-slate-100 ${result && !result.intact && result.first_broken_entry === e.id ? "bg-red-50" : ""}`}>
                  <td className="td">{e.id}</td><td className="td whitespace-nowrap text-xs">{fmtTime(e.ts)}</td><td className="td text-xs">{e.actor}</td>
                  <td className="td"><Badge>{e.role}</Badge></td><td className="td text-xs font-medium">{e.action}</td><td className="td text-xs">{e.detail}</td>
                  <td className="td font-mono text-[10px] text-slate-500" title={e.hash}>{e.hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}
