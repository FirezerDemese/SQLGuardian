import { AIPanel } from "../components/ai/AIPanel";

export function InstanceAiPage() {
  return (
    <div className="p-9">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text-primary">AI Brain</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Explain current health, get remediation scripts, or ask a free-form question.
        </p>
      </div>
      <AIPanel />
    </div>
  );
}
