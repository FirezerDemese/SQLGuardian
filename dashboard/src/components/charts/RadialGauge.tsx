import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { SEVERITY_HEX } from "../../types/severity";
import type { Severity } from "../../types/api";

export function RadialGauge({
  label,
  pct,
  severity,
  sub,
}: {
  label: string;
  pct: number;
  severity: Severity;
  sub?: string;
}) {
  const data = [{ name: label, value: pct, fill: SEVERITY_HEX[severity] }];

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-[120px] w-[120px]">
        <RadialBarChart
          width={120}
          height={120}
          cx="50%"
          cy="50%"
          innerRadius="72%"
          outerRadius="100%"
          barSize={10}
          data={data}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar
            background={{ fill: "var(--surface-sunken)" }}
            dataKey="value"
            cornerRadius={6}
            angleAxisId={0}
          />
        </RadialBarChart>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold text-text-primary">{pct}%</span>
        </div>
      </div>
      <div className="mt-1 text-xs font-medium uppercase tracking-wide text-text-tertiary">
        {label}
      </div>
      {sub && <div className="text-xs text-text-tertiary">{sub}</div>}
    </div>
  );
}
