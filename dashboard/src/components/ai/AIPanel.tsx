import { useState } from "react";
import { Stethoscope, Wrench, MessageCircleQuestion } from "lucide-react";
import { cn } from "../../lib/cn";
import { ExplainView } from "./ExplainView";
import { SuggestView } from "./SuggestView";
import { AskView } from "./AskView";

type Mode = "explain" | "suggest" | "ask";

const MODES: { id: Mode; label: string; icon: typeof Stethoscope }[] = [
  { id: "explain", label: "Explain", icon: Stethoscope },
  { id: "suggest", label: "Suggest Fixes", icon: Wrench },
  { id: "ask", label: "Ask a Question", icon: MessageCircleQuestion },
];

export function AIPanel() {
  const [mode, setMode] = useState<Mode>("explain");

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <div className="flex gap-2 rounded-lg border border-border-subtle bg-surface-card p-1">
        {MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              mode === m.id
                ? "bg-accent-bg text-accent"
                : "text-text-secondary hover:bg-surface-sunken"
            )}
          >
            <m.icon className="h-4 w-4" />
            {m.label}
          </button>
        ))}
      </div>

      {mode === "explain" && <ExplainView />}
      {mode === "suggest" && <SuggestView />}
      {mode === "ask" && <AskView />}
    </div>
  );
}
