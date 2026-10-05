"use client";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Mission-capable aircraft per day, without and with the plan. */
export function ForecastChart({ days, without, withPlan, total, target, withLabel = "With recommended plan", height = 260 }:
  { days: number[]; without: number[]; withPlan: number[]; total: number; target?: number; withLabel?: string; height?: number }) {
  const data = days.map((d, i) => ({ day: d, without: without[i], withPlan: withPlan[i] }));
  return (
    <div style={{ height }} aria-label="Readiness forecast chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
          <XAxis dataKey="day" tick={{ fontSize: 11 }} label={{ value: "Days from today", position: "insideBottom", offset: -8, fontSize: 11 }} />
          <YAxis domain={[0, total]} allowDecimals={false} tick={{ fontSize: 11 }} label={{ value: "Mission-capable aircraft", angle: -90, position: "insideLeft", fontSize: 11, dy: 60 }} />
          <Tooltip formatter={(v: any, n: any) => [`${v} of ${total}`, n]} labelFormatter={(d) => `Day ${d}`} />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
          {target !== undefined && <ReferenceLine y={target * total} stroke="#94a3b8" strokeDasharray="6 4" label={{ value: `${Math.round(target * 100)}% target`, fontSize: 10, fill: "#64748b", position: "insideTopRight" }} />}
          <Line type="stepAfter" dataKey="without" name="Without action" stroke="#dc2626" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="stepAfter" dataKey="withPlan" name={withLabel} stroke="#16a34a" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
