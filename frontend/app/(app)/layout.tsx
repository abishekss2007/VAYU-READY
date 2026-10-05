"use client";
import { BookOpen, ChevronLeft, ChevronRight, LogOut, Menu, Radio, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DemoGuide } from "@/components/demo-guide";
import { Button, cn, Loading, Modal } from "@/components/ui";
import { api, getToken } from "@/lib/api";
import { canSee, HOME, NAV, ROLE_NAME } from "@/lib/nav";
import { useSession } from "@/lib/session";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { me, setMe, logout, toasts, live, classification, notify } = useSession();
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [guide, setGuide] = useState(false);
  const [notice, setNotice] = useState<any>(null);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    if (!me) api("/auth/me").then(setMe).catch(() => router.replace("/login"));
  }, [me, router, setMe]);

  useEffect(() => {
    if (me && !canSee(me.role, path)) router.replace(HOME[me.role]);
    setOpen(false);
  }, [me, path, router]);

  // DPDP notice: shown on first login until acknowledged
  useEffect(() => {
    if (me && !me.notice_acknowledged) api("/me/notice").then(setNotice).catch(() => {});
  }, [me]);

  useEffect(() => { setGuide(localStorage.getItem("vayu_guide") === "1"); }, []);
  const toggleGuide = () => setGuide((g) => { localStorage.setItem("vayu_guide", g ? "0" : "1"); return !g; });

  if (!me) return <Loading label="Checking your session..." />;
  const links = NAV.filter((n) => n.roles.includes(me.role));

  return (
    <div className="flex min-h-screen flex-col">
      <div className="sticky top-0 z-40 bg-amber-100 py-1 text-center text-xs font-semibold tracking-wide text-amber-900" data-testid="classification-banner">{classification}</div>
      <div className="flex flex-1">
        {/* Sidebar: fixed on tablet and up, slide-over on phones */}
        <aside className={cn("fixed inset-y-0 left-0 z-30 w-56 shrink-0 transform bg-navy pt-7 text-slate-100 transition lg:static lg:translate-x-0 lg:pt-0", open ? "translate-x-0" : "-translate-x-full")}>
          <div className="flex items-center justify-between px-4 py-4">
            <div>
              <div className="text-lg font-semibold tracking-wide">VAYU-READY</div>
              <div className="text-[11px] text-slate-300">Fleet availability</div>
            </div>
            <button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
          </div>
          <nav className="space-y-0.5 px-2" aria-label="Main">
            {links.map((n) => {
              const active = path === n.href || path.startsWith(n.href + "/");
              return (
                <Link key={n.href} href={n.href}
                  className={cn("block rounded-md px-3 py-2.5 text-sm", active ? "bg-sky-500/20 font-medium text-white ring-1 ring-sky-400/40" : "text-slate-200 hover:bg-white/10")}>
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-6 border-t border-white/10 px-4 py-3 text-xs text-slate-300">
            <div className="font-medium text-white">{me.name}</div>
            <div>{ROLE_NAME[me.role]}{me.squadron_code ? ` · ${me.squadron_code}` : ""}</div>
            <button onClick={logout} className="mt-2 inline-flex items-center gap-1 text-sky-300 hover:text-white"><LogOut className="h-3.5 w-3.5" />Log out</button>
          </div>
        </aside>
        {open && <div className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden" onClick={() => setOpen(false)} />}

        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-2">
            <div className="flex items-center gap-1">
              <button className="rounded p-1.5 text-navy hover:bg-slate-100 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
              {/* Same as the browser's back and forward buttons */}
              <Button variant="outline" size="sm" onClick={() => router.back()} aria-label="Go back" title="Go back to the previous screen" data-testid="nav-back"><ChevronLeft className="h-4 w-4" /><span className="hidden sm:inline">Back</span></Button>
              <Button variant="outline" size="sm" onClick={() => router.forward()} aria-label="Go next" title="Go forward to the next screen" data-testid="nav-next"><span className="hidden sm:inline">Next</span><ChevronRight className="h-4 w-4" /></Button>
            </div>
            <div className="hidden items-center gap-1.5 text-xs text-slate-500 sm:flex" title="Live updates over WebSocket">
              <Radio className={cn("h-3.5 w-3.5", live ? "text-ok" : "text-slate-400")} />
              {live ? "Live updates on" : "Live updates off"}
              <span className="hidden sm:inline">· Offline deployment, no external calls</span>
            </div>
            <Button variant="outline" size="sm" onClick={toggleGuide}><BookOpen className="h-3.5 w-3.5" />Demo guide</Button>
          </header>
          {me.read_only && <div className="border-b border-sky-200 bg-sky-50 px-4 py-1.5 text-xs font-medium text-sky-800">Read-only access</div>}
          <main className="mx-auto max-w-7xl p-4">{canSee(me.role, path) ? children : <Loading label="Opening your home screen..." />}</main>
        </div>
      </div>

      {guide && <DemoGuide onClose={toggleGuide} />}

      <div className="fixed bottom-4 right-4 z-50 flex w-[min(92vw,24rem)] flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cn("rounded-md border px-3 py-2 text-sm shadow-lg", t.kind === "error" ? "border-red-200 bg-red-50 text-red-800" : "border-green-200 bg-green-50 text-green-800")}>{t.text}</div>
        ))}
      </div>

      {notice && (
        <Modal title="Privacy notice / गोपनीयता सूचना" onClose={() => setNotice(null)}>
          <div className="space-y-3 text-sm text-slate-700">
            <p>{notice.en.body}</p>
            <p lang="hi">{notice.hi.body}</p>
            <Button onClick={async () => {
              try { await api("/me/notice-ack", { method: "POST" }); setMe({ ...me, notice_acknowledged: true }); setNotice(null); }
              catch (e: any) { notify(e.message, "error"); }
            }}>I have read this / मैंने पढ़ लिया</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
