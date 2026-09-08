import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { WaitStat } from "../../types/api";

export function WaitBarsChart({ waits }: { waits: WaitStat[] }) {
  const data = [...waits]
    .sort((a, b) => b.wait_seconds - a.wait_seconds)
    .map((w) => ({
      name: w.wait_type,
      Resource: parseFloat(w.resource_wait_seconds.toFixed(2)),
      Signal: parseFloat(w.signal_wait_seconds.toFixed(2)),
    }));

  if (data.length === 0) {
    return <p className="text-sm text-text-tertiary">No wait statistics recorded.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 0, right: 20, left: 30, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
        <XAxis
          type="number"
          unit="s"
          tick={{ fontSize: 11, fill: "var(--text-tertiary)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={180}
          tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
          formatter={(value: number, name: string) => [`${value}s`, name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Resource" fill="#7c3aed" radius={[0, 3, 3, 0]} />
        <Bar dataKey="Signal" fill="#a78bfa" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
