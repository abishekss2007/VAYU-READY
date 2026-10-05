"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/session";
import { Advisory, Button, Modal } from "./ui";

const CHOICES = [
  { v: "Inspect", label: "Inspect", hint: "Send a technician to look at it" },
  { v: "Schedule", label: "Schedule engine change", hint: "Plan the fix in the maintenance schedule" },
  { v: "FalseAlarm", label: "False alarm", hint: "Logged against the model's false-alarm rate" },
];

export function ReviewDialog({ alert, onClose, onDone }: { alert: any; onClose: () => void; onDone: (r: any, decision: string) => void }) {
  const [decision, setDecision] = useState("Schedule");
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  return (
    <Modal title={`Review alert ${alert.id} · ${alert.tail_no}`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-slate-700">{alert.message}</p>
        <fieldset className="space-y-2">
          <legend className="label">Your decision</legend>
          {CHOICES.map((c) => (
            <label key={c.v} className={`flex cursor-pointer items-start gap-2 rounded-md border p-2.5 text-sm ${decision === c.v ? "border-sky-400 bg-sky-50" : "border-slate-200"}`}>
              <input type="radio" name="decision" className="mt-1" checked={decision === c.v} onChange={() => setDecision(c.v)} />
              <span><span className="font-medium">{c.label}</span><span className="block text-xs text-slate-500">{c.hint}</span></span>
            </label>
          ))}
        </fieldset>
        <div>
          <label className="label" htmlFor="note">Note</label>
          <textarea id="note" className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you see? What happens next?" />
        </div>
        <Advisory />
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button busy={busy === "review"} onClick={() => run("review", () => api(`/alerts/${alert.id}/review`, { body: { decision, note } }), (r) => onDone(r, decision))}>Save review</Button>
        </div>
      </div>
    </Modal>
  );
}
