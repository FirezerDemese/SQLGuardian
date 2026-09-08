import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Dialog } from "../primitives/Dialog";
import { api } from "../../api/endpoints";
import { queryKeys } from "../../api/queryKeys";
import { ApiError } from "../../api/client";
import type { RegisterInstanceRequest } from "../../types/api";

const emptyForm: RegisterInstanceRequest = {
  name: "",
  host: "",
  port: 1433,
  user: "",
  password: "",
  database: "master",
  is_default: false,
};

export function AddInstanceDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [form, setForm] = useState<RegisterInstanceRequest>(emptyForm);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: api.registerInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.instances });
      setForm(emptyForm);
      onOpenChange(false);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(form);
  }

  function field<K extends keyof RegisterInstanceRequest>(key: K) {
    return {
      value: form[key] ?? "",
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        const raw = e.target.value;
        setForm((f) => ({
          ...f,
          [key]: key === "port" ? Number(raw) : raw,
        }));
      },
    };
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Add SQL Server instance">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <LabeledInput label="Instance name" placeholder="prod-01" required {...field("name")} />
        <LabeledInput label="Host" placeholder="10.0.0.5 or hostname" required {...field("host")} />
        <div className="grid grid-cols-2 gap-3">
          <LabeledInput label="Port" type="number" required {...field("port")} />
          <LabeledInput label="Database" placeholder="master" {...field("database")} />
        </div>
        <LabeledInput label="User" required {...field("user")} />
        <LabeledInput label="Password" type="password" required {...field("password")} />

        <label className="mt-1 flex items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={!!form.is_default}
            onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
            className="h-4 w-4 rounded border-border accent-accent"
          />
          Set as default instance
        </label>

        {mutation.isError && (
          <p className="text-sm text-severity-critical">
            {mutation.error instanceof ApiError
              ? mutation.error.message
              : "Failed to register instance."}
          </p>
        )}

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg border border-border-subtle px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-sunken"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {mutation.isPending ? "Connecting..." : "Add instance"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function LabeledInput({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1 text-sm text-text-secondary">
      {label}
      <input
        {...props}
        className="rounded-lg border border-border-subtle bg-surface-card px-3 py-1.5 text-sm text-text-primary focus:border-accent focus:outline-none"
      />
    </label>
  );
}
