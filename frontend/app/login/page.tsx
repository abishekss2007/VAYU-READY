"use client";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, ErrorBox } from "@/components/ui";
import { api, clearToken, getToken, setToken } from "@/lib/api";
import { HOME, Role } from "@/lib/nav";
import { useSession } from "@/lib/session";

// Demo mode: one-tap logins for judges. Set NEXT_PUBLIC_DEMO_MODE=off at build time for a real deployment.
const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE !== "off";
const DEMO_PASSWORD = "demo123";
const DEMO_CODE = "482913";
const DEMO: { id: string; role: string; sees: string }[] = [
  { id: "co", role: "Squadron Commander", sees: "Readiness dashboard, approves the plan" },
  { id: "engo", role: "Engineering Officer", sees: "Aircraft health, alerts, schedule" },
  { id: "tech", role: "Technician", sees: "My tasks, log a defect" },
  { id: "logo", role: "Logistics Officer", sees: "Spares and indents" },
  { id: "brd", role: "BRD Planner", sees: "Overhaul tracker" },
  { id: "fso", role: "Flight Safety Officer", sees: "Read-only trends" },
  { id: "admin", role: "Admin", sees: "Users, reset demo" },
  { id: "auditor", role: "Auditor", sees: "Audit trail, verify chain" },
  { id: "hq", role: "Air HQ Leadership", sees: "All squadrons" },
];

export default function Login() {
  const { classification } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [otpToken, setOtpToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const expired = typeof window !== "undefined" && new URLSearchParams(location.search).has("expired");

  // Already logged in (for example after pressing Back)? Go straight back into the app.
  useEffect(() => {
    if (!getToken()) return;
    api("/auth/me").then((me) => location.replace(HOME[me.role as Role])).catch(() => clearToken());
  }, []);

  async function finish(token: string) {
    setToken(token);
    const me = await api("/auth/me");
    location.href = HOME[me.role as Role];
  }

  async function login(em: string, pw: string) {
    setBusy(true);
    setError(null);
    try {
      const r = await api("/auth/login", { body: { email: em, password: pw } });
      if (r.stage === "otp") {
        setOtpToken(r.token);
        if (DEMO_MODE && em.endsWith("@vayu.demo")) setCode(DEMO_CODE); // demo: the code is filled in, the judge just presses Verify
      } else await finish(r.token);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // One tap on a demo role: fills the form and logs in.
  function demoLogin(id: string) {
    const em = `${id}@vayu.demo`;
    setEmail(em);
    setPassword(DEMO_PASSWORD);
    login(em, DEMO_PASSWORD);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!otpToken) return login(email, password);
    setBusy(true);
    setError(null);
    try {
      {
        const r = await api("/auth/otp", { body: { code }, token: otpToken });
        await finish(r.token);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <div className="bg-amber-100 py-1 text-center text-xs font-semibold tracking-wide text-amber-900">{classification}</div>
      <div className="flex flex-1 items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="mb-5 text-center">
            <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-navy text-white"><ShieldCheck className="h-6 w-6" /></div>
            <h1 className="text-2xl font-semibold text-navy">VAYU-READY</h1>
            <p className="text-sm text-slate-500">Which aircraft can fly, and what needs attention now?</p>
          </div>
          <form onSubmit={submit} className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            {expired && !error && <p className="text-xs text-amber-700">Your 15-minute session ended. Please log in again.</p>}
            {error && <ErrorBox>{error}</ErrorBox>}
            {!otpToken ? (
              <>
                <div>
                  <label className="label" htmlFor="email">Email</label>
                  <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div>
                  <label className="label" htmlFor="password">Password</label>
                  <input id="password" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
                </div>
                <Button className="w-full" busy={busy} type="submit">Log in</Button>
              </>
            ) : (
              <>
                <p className="text-sm text-slate-600">Step 2 of 2. Enter the 6-digit code for <b>{email}</b>.</p>
                <div>
                  <label className="label" htmlFor="code">One-time code</label>
                  <input id="code" className="input text-center text-lg tracking-[0.4em]" inputMode="numeric" maxLength={6} autoFocus required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
                </div>
                {DEMO_MODE && <p className="rounded bg-sky-50 px-2 py-1.5 text-xs text-sky-800">Demo code: <b className="tracking-widest">{DEMO_CODE}</b> (already filled in)</p>}
                <Button className="w-full" busy={busy} type="submit">Verify code</Button>
                <button type="button" className="w-full text-xs text-sky-700 hover:underline" onClick={() => { setOtpToken(null); setCode(""); setError(null); }}>Back to login</button>
              </>
            )}
          </form>
          {DEMO_MODE && !otpToken && (
            <div className="mt-4 rounded-lg border border-sky-200 bg-white p-3" data-testid="demo-logins">
              <p className="text-sm font-semibold text-navy">Demo accounts: tap a role to log in</p>
              <p className="mb-2 text-xs text-slate-500">
                Password for every account: <b className="text-slate-800">{DEMO_PASSWORD}</b> · One-time code: <b className="text-slate-800">{DEMO_CODE}</b>
              </p>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {DEMO.map((d) => (
                  <button key={d.id} type="button" disabled={busy} onClick={() => demoLogin(d.id)}
                    className="min-h-[44px] rounded-md border border-slate-200 px-2.5 py-1.5 text-left hover:border-sky-400 hover:bg-sky-50 disabled:opacity-50">
                    <span className="block text-xs font-semibold text-navy">{d.role}</span>
                    <span className="block text-[11px] text-slate-500">{d.id}@vayu.demo · {d.sees}</span>
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-400">Start with Squadron Commander. Synthetic data only.</p>
            </div>
          )}
          <p className="mt-4 text-center text-xs text-slate-400">Runs offline inside the base network. Synthetic demo data only.</p>
        </div>
      </div>
    </div>
  );
}
