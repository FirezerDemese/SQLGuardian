import { useState } from "react";
import { Send } from "lucide-react";
import { useAiAsk } from "../../hooks/useAi";
import { Card } from "../primitives/Card";
import { AiMeta } from "./AiMeta";

export function AskView() {
  const [question, setQuestion] = useState("");
  const mutation = useAiAsk();
  const result = mutation.data;
  const canSubmit = question.trim().length >= 3 && !mutation.isPending;

  function submit() {
    if (!canSubmit) return;
    mutation.mutate({ question: question.trim() });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Ask anything about this server's current state..."
          className="flex-1 rounded-lg border border-border-subtle bg-surface-card px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={!canSubmit}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {mutation.isPending ? "Thinking..." : "Ask"}
        </button>
      </div>

      {mutation.isError && (
        <p className="text-sm text-severity-critical">Failed to reach the AI engine.</p>
      )}
      {result?.error && <p className="text-sm text-severity-critical">{result.error}</p>}

      {result && !result.error && (
        <Card>
          <p className="text-sm text-text-tertiary">"{result.question}"</p>
          <p className="mt-2 text-sm text-text-primary">{result.answer}</p>
          {result.supporting_data && (
            <p className="mt-3 text-xs text-text-tertiary">
              Supporting data: {result.supporting_data}
            </p>
          )}
          {result.follow_up_suggestion && (
            <p className="mt-1 text-xs text-text-tertiary">
              Suggested follow-up: {result.follow_up_suggestion}
            </p>
          )}
          <AiMeta generatedAt={result.generated_at} model={result.model} />
        </Card>
      )}
    </div>
  );
}
