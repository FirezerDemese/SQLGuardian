import { Database } from "lucide-react";

export function EmptyState({
  title,
  description,
  icon: Icon = Database,
}: {
  title: string;
  description?: string;
  icon?: React.ElementType;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-subtle bg-surface-card py-16 text-center">
      <Icon className="mb-3 h-8 w-8 text-text-tertiary" />
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="mt-1 text-sm text-text-tertiary">{description}</p>}
    </div>
  );
}
