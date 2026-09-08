import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Server } from "lucide-react";
import { useInstances } from "../../hooks/useInstances";

export function InstanceSwitcher({ current }: { current: string }) {
  const { data } = useInstances();
  const navigate = useNavigate();
  const instanceNames = data?.instances ?? [];

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-card px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-surface-sunken">
          <Server className="h-3.5 w-3.5 text-text-tertiary" />
          {current}
          <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={4}
          className="z-50 min-w-[200px] rounded-lg border border-border-subtle bg-surface-card p-1 shadow-lg"
        >
          {instanceNames.map((name) => (
            <DropdownMenu.Item
              key={name}
              onSelect={() => navigate(`/instance/${encodeURIComponent(name)}`)}
              className="cursor-pointer rounded-md px-3 py-2 text-sm text-text-primary outline-none hover:bg-surface-sunken data-[highlighted]:bg-surface-sunken"
            >
              {name}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
