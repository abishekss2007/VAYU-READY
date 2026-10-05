"use client";
// Small shadcn/ui-style building blocks (kept local so nothing is fetched at runtime).
import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import * as React from "react";

export const cn = clsx;

export function Card({ className, children, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("min-w-0 rounded-lg border border-slate-200 bg-white shadow-sm", className)} {...p}>{children}</div>;
}

export function CardHeader({ title, sub, right }: { title: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-navy">{title}</h2>
        {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "outline" | "ghost" | "danger" | "success"; size?: "sm" | "md"; busy?: boolean };
export function Button({ variant = "primary", size = "md", busy, className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: "bg-navy text-white hover:bg-navy-700",
    success: "bg-ok text-white hover:bg-green-700",
    danger: "bg-crit text-white hover:bg-red-700",
    outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    ghost: "text-sky-700 hover:bg-sky-50",
  }[variant];
  return (
    <button
      className={cn("inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "min-h-[32px] px-2.5 text-xs" : "min-h-[40px] px-4 text-sm", v, className)}
      disabled={disabled || busy} {...p}>
      {busy && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

const TONE: Record<string, string> = {
  red: "bg-red-50 text-red-700 border-red-200", amber: "bg-amber-50 text-amber-800 border-amber-200",
  green: "bg-green-50 text-green-700 border-green-200", blue: "bg-sky-50 text-sky-700 border-sky-200",
  grey: "bg-slate-100 text-slate-600 border-slate-200",
};
export function Badge({ tone = "grey", children }: { tone?: keyof typeof TONE | string; children: React.ReactNode }) {
  return <span className={cn("inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium", TONE[tone] || TONE.grey)}>{children}</span>;
}

// Status colours only where they carry meaning: red = critical, amber = warning, green = OK.
export const severityTone = (s: string) => (s === "Critical" ? "red" : s === "Warning" ? "amber" : "blue");
export const statusTone = (s: string) => (s === "MC" ? "green" : s === "PMC" ? "amber" : s === "AOG" ? "red" : "amber");
export const healthTone = (h: number) => (h >= 60 ? "green" : h >= 30 ? "amber" : "red");
export const healthBg = (h: number) => (h >= 60 ? "bg-green-50 border-green-300" : h >= 30 ? "bg-amber-50 border-amber-300" : "bg-red-50 border-red-300");

export function Loading({ label = "Loading..." }: { label?: string }) {
  return <div className="flex items-center gap-2 p-6 text-sm text-slate-500" role="status"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="p-6 text-center text-sm text-slate-500">{children}</div>;
}

export function ErrorBox({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{children}</div>;
}

export function Advisory() {
  return <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">Advisory. Final decision rests with the authorised engineer.</p>;
}

export function Stat({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "red" | "amber" | "green" }) {
  return (
    <Card className="px-4 py-3">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold", tone === "red" ? "text-crit" : tone === "amber" ? "text-warn" : tone === "green" ? "text-ok" : "text-navy")}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

export function PageTitle({ title, question, right }: { title: string; question?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-navy">{title}</h1>
        {question && <p className="text-sm text-slate-500">{question}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{right}</div>
    </div>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-navy">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-slate-500 hover:bg-slate-100"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export function TableWrap({ children }: { children: React.ReactNode }) {
  // Wide tables scroll sideways inside their card on a tablet instead of squeezing the columns.
  return <div className="overflow-x-auto"><table className="w-full min-w-[680px] border-collapse">{children}</table></div>;
}

/** Loads data from the API with loading and error states. Reloads when deps change. */
export function useLoad<T = any>(loader: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    let live = true;
    loader()
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n]);
  return { data, error, loading, reload: () => setN((x) => x + 1) };
}
