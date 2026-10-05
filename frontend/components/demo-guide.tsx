"use client";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./ui";

// The 3-minute demo script (same as DEMO.md), shown one step at a time.
const STEPS = [
  { who: "Commander · co@vayu.demo", time: "30 s", do: "Open the Readiness Dashboard.", say: "14 of 18 aircraft are mission-capable, but the forecast drops to 11 in 9 days. Fleet Health Score 71, and here are the 5 reasons." },
  { who: "Engineering Officer · engo@vayu.demo", time: "45 s", do: "Aircraft Health → open TAIL-SQ7-114 → Review alert → Schedule engine change.", say: "Engine 2 has 18 cycles left. SHAP shows HPC outlet temperature and fan speed drift. Review alert: score goes to 76." },
  { who: "Logistics Officer · logo@vayu.demo", time: "30 s", do: "Spares and Indents → show IND-012 (auto-raised) → Receive IND-010 (HYD-ACT-22).", say: "The HPC module has a 21-day lead time and zero stock. The indent was raised automatically before anyone asked." },
  { who: "Engineering Officer · engo@vayu.demo", time: "15 s", do: "Open TAIL-SQ7-105 → Change status → Mission-capable, with a reason.", say: "The part is in, the engineer releases the aircraft. Score 83." },
  { who: "Engineering Officer, then Commander", time: "45 s", do: "Schedule and What-If → Run optimiser. Then as co@vayu.demo → Approve plan.", say: "Servicing 3 aircraft this week lifts 30-day availability from 11 to 16." },
  { who: "Auditor · auditor@vayu.demo", time: "30 s", do: "Audit Trail → Verify chain. Then Model Cards and Compliance.", say: "Every action is hash-chained. The AI is advisory only, the system runs offline, and here is the compliance checklist." },
];

export function DemoGuide({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  useEffect(() => { setI(Number(localStorage.getItem("vayu_guide_step") || 0)); }, []);
  const go = (n: number) => { const v = Math.max(0, Math.min(STEPS.length - 1, n)); setI(v); localStorage.setItem("vayu_guide_step", String(v)); };
  const s = STEPS[i];
  return (
    <div className="fixed bottom-4 left-4 z-40 w-[min(92vw,22rem)] rounded-lg border border-sky-300 bg-white shadow-xl lg:left-60">
      <div className="flex items-center justify-between rounded-t-lg bg-sky-50 px-3 py-2">
        <div className="text-xs font-semibold text-sky-900">Demo guide · step {i + 1} of {STEPS.length} · {s.time}</div>
        <button onClick={onClose} aria-label="Close demo guide"><X className="h-4 w-4 text-sky-900" /></button>
      </div>
      <div className="space-y-2 p-3 text-sm">
        <div className="text-xs font-medium text-slate-500">{s.who}</div>
        <div><span className="font-medium text-navy">Do:</span> {s.do}</div>
        <div className="rounded bg-slate-50 p-2 text-slate-700">“{s.say}”</div>
        <div className="flex justify-between pt-1">
          <Button variant="outline" size="sm" onClick={() => go(i - 1)} disabled={i === 0}>Back</Button>
          <Button size="sm" onClick={() => go(i + 1)} disabled={i === STEPS.length - 1}>Next step</Button>
        </div>
      </div>
    </div>
  );
}
