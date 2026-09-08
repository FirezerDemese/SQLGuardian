import { Card } from "../primitives/Card";
import { ProgressBar } from "../primitives/ProgressBar";
import type { DiskUsage } from "../../types/api";

export function DiskPanel({ disk }: { disk: DiskUsage }) {
  return (
    <Card>
      <h3 className="mb-4 text-sm font-semibold text-text-primary">Disk &amp; Storage</h3>
      {disk.volumes.length === 0 ? (
        <p className="text-sm text-text-tertiary">No volumes reported.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {disk.volumes.map((v) => (
            <ProgressBar
              key={v.volume_mount_point}
              label={`${v.volume_mount_point} (${v.logical_volume_name || v.file_system_type})`}
              valueLabel={`${v.used_gb.toFixed(0)} / ${v.total_gb.toFixed(0)} GB (${v.used_pct}%)`}
              pct={v.used_pct}
              severity={v.severity}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
