import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { TOOL_LABELS } from "@/lib/format";

import type { AssistantTurn, Turn } from "./types";

type MessageBubbleProps = {
  turn: Turn;
  selected: boolean;
  onSelect: () => void;
};

export function MessageBubble({ turn, selected, onSelect }: MessageBubbleProps) {
  if (turn.role === "user") {
    return (
      <div className="rise flex justify-end">
        <p className="max-w-[85%] rounded-[6px] rounded-br-[2px] bg-ink px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap text-paper">
          {turn.content}
        </p>
      </div>
    );
  }
  return <AssistantMessage turn={turn} selected={selected} onSelect={onSelect} />;
}

function AssistantMessage({ turn, selected, onSelect }: { turn: AssistantTurn; selected: boolean; onSelect: () => void }) {
  const running = turn.steps.find((step) => !step.trace);
  const alerts = turn.response
    ? turn.response.unverified_amounts.length + turn.response.unknown_rules.length + turn.response.unknown_products.length
    : 0;
  const verifiedRules = turn.response?.citations.filter((c) => c.from_calculation).length ?? 0;

  return (
    <div className="rise flex">
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label="Afficher le détail de cette réponse dans le panneau Sous le capot"
        className={`group w-full max-w-[92%] rounded-[6px] border px-4 py-3 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ochre focus-visible:outline-none ${
          selected ? "border-ink/60 bg-paper/70" : "border-transparent hover:border-rule"
        }`}
      >
        <p className="mb-1.5 font-mono text-[10.5px] tracking-[0.18em] text-ink-faint uppercase">Assistant</p>

        {turn.status === "error" ? (
          <p className="text-[15px] text-vermilion">{turn.error}</p>
        ) : turn.draft ? (
          <div className={`prose-ledger text-[15px] leading-relaxed ${turn.status === "streaming" ? "caret" : ""}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.draft}</ReactMarkdown>
          </div>
        ) : (
          <p className="scanning rounded-[3px] py-1 font-mono text-[12.5px] text-ink-soft">
            {running ? `${TOOL_LABELS[running.name] ?? running.name}…` : "Analyse de la question…"}
          </p>
        )}

        {turn.status !== "error" && (turn.steps.length > 0 || turn.response) && (
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-dashed border-rule pt-2 font-mono text-[11px] text-ink-soft">
            {turn.steps.length > 0 && (
              <span>
                {turn.steps.length} appel{turn.steps.length > 1 ? "s" : ""} au moteur
              </span>
            )}
            {verifiedRules > 0 && (
              <span className="text-green">
                ✓ {verifiedRules} règle{verifiedRules > 1 ? "s" : ""} vérifiée{verifiedRules > 1 ? "s" : ""}
              </span>
            )}
            {turn.response && alerts === 0 && <span className="text-green">✓ contrôles passés</span>}
            {alerts > 0 && (
              <span className="text-vermilion">
                ⚠ {alerts} élément{alerts > 1 ? "s" : ""} non vérifié{alerts > 1 ? "s" : ""}
              </span>
            )}
            <span className="ml-auto text-ink-faint opacity-0 transition-opacity group-hover:opacity-100">
              détail →
            </span>
          </div>
        )}
      </button>
    </div>
  );
}
