"use client";

import { useEffect, useRef, useState } from "react";

import { type ChatMessage, streamChat } from "@/lib/api";

import { MessageBubble } from "./MessageBubble";
import type { AssistantTurn, Turn } from "./types";
import { Suggestions } from "./Suggestions";
import { UnderTheHood } from "./UnderTheHood";

const MAX_MESSAGES = 20; // limite de l'API
const MAX_LENGTH = 4000;

type AssistantViewProps = {
  chatEnabled: boolean;
  draftQuestion: string | null;
  onDraftConsumed: () => void;
};

export function AssistantView({ chatEnabled, draftQuestion, onDraftConsumed }: AssistantViewProps) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const busy = turns.some((turn) => turn.role === "assistant" && turn.status === "streaming");
  const assistantTurns = turns.filter((turn): turn is AssistantTurn => turn.role === "assistant");
  const selected = assistantTurns.find((turn) => turn.id === selectedId) ?? assistantTurns.at(-1);

  useEffect(() => {
    if (draftQuestion === null) return;
    inputRef.current?.focus();
    // La question préparée par le simulateur remplit la zone de saisie ; l'utilisateur garde la main pour l'envoyer.
    queueMicrotask(() => {
      setInput(draftQuestion);
      onDraftConsumed();
    });
  }, [draftQuestion, onDraftConsumed]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const updateAssistant = (id: string, change: (turn: AssistantTurn) => AssistantTurn) =>
    setTurns((current) =>
      current.map((turn) => (turn.id === id && turn.role === "assistant" ? change(turn) : turn)),
    );

  const send = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;

    const history: ChatMessage[] = turns.flatMap((turn): ChatMessage[] => {
      if (turn.role === "user") return [{ role: "user", content: turn.content.slice(0, MAX_LENGTH) }];
      if (turn.status === "done" && turn.response) {
        return [{ role: "assistant", content: turn.response.answer.slice(0, MAX_LENGTH) }];
      }
      return [];
    });
    const messages = [...history, { role: "user" as const, content: text.slice(0, MAX_LENGTH) }].slice(
      -MAX_MESSAGES,
    );
    while (messages.length > 1 && messages[0].role !== "user") messages.shift();

    const userTurn: Turn = { id: crypto.randomUUID(), role: "user", content: text };
    const assistantId = crypto.randomUUID();
    const assistantTurn: AssistantTurn = {
      id: assistantId,
      role: "assistant",
      status: "streaming",
      draft: "",
      steps: [],
      startedAt: performance.now(),
    };
    setTurns((current) => [...current, userTurn, assistantTurn]);
    setSelectedId(assistantId);
    setInput("");

    const controller = new AbortController();
    abortRef.current = controller;
    await streamChat(
      messages,
      {
        onDelta: (delta) => updateAssistant(assistantId, (turn) => ({ ...turn, draft: turn.draft + delta })),
        onToolCall: (name, args) =>
          updateAssistant(assistantId, (turn) => ({
            ...turn,
            draft: "", // un texte suivi d'appels d'outils n'était qu'un préambule
            steps: [...turn.steps, { name, arguments: args }],
          })),
        onToolResult: (trace) =>
          updateAssistant(assistantId, (turn) => {
            const index = turn.steps.findIndex((step) => step.name === trace.name && !step.trace);
            if (index === -1) return turn;
            const steps = turn.steps.map((step, i) => (i === index ? { ...step, trace } : step));
            return { ...turn, steps };
          }),
        onDone: (response) =>
          updateAssistant(assistantId, (turn) => ({
            ...turn,
            status: "done",
            response,
            draft: response.answer,
            durationMs: performance.now() - turn.startedAt,
          })),
        onError: (_status, detail) =>
          updateAssistant(assistantId, (turn) => ({
            ...turn,
            status: "error",
            error: detail,
            durationMs: performance.now() - turn.startedAt,
          })),
      },
      controller.signal,
    );
    updateAssistant(assistantId, (turn) =>
      turn.status === "streaming" ? { ...turn, status: "error", error: "Réponse interrompue." } : turn,
    );
  };

  const stop = () => abortRef.current?.abort();

  return (
    <div className="grid h-full gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
      <section aria-label="Conversation" className="flex min-h-[70vh] flex-col rounded-[6px] border border-rule bg-card/80 shadow-[0_1px_0_var(--rule),0_18px_40px_-28px_rgba(28,26,21,0.35)] lg:h-[calc(100vh-15rem)]">
        <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-5 py-6 sm:px-7" aria-live="polite">
          {turns.length === 0 ? (
            <Suggestions onPick={(question) => void send(question)} disabled={!chatEnabled} />
          ) : (
            turns.map((turn) => (
              <MessageBubble
                key={turn.id}
                turn={turn}
                selected={turn.role === "assistant" && turn.id === selected?.id}
                onSelect={() => setSelectedId(turn.id)}
              />
            ))
          )}
        </div>

        <form
          className="border-t border-rule p-3 sm:p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
        >
          <div className="flex items-end gap-2 rounded-[5px] border border-ink/70 bg-paper/60 p-2 focus-within:border-ink focus-within:ring-2 focus-within:ring-ochre/40">
            <label htmlFor="question" className="sr-only">
              Votre question
            </label>
            <textarea
              id="question"
              ref={inputRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(input);
                }
              }}
              rows={input.split("\n").length > 2 ? 4 : 2}
              maxLength={MAX_LENGTH}
              disabled={!chatEnabled}
              placeholder={
                chatEnabled
                  ? "Ex. : pourquoi le contrat SI-RESILIE donne-t-il une reprise ?"
                  : "Assistant désactivé : configurez LLM_API_KEY côté API."
              }
              className="flex-1 resize-none bg-transparent px-2 py-1 text-[15px] leading-relaxed placeholder:text-ink-faint focus:outline-none disabled:cursor-not-allowed"
            />
            {busy ? (
              <button
                type="button"
                onClick={stop}
                className="rounded-[4px] border border-vermilion px-4 py-2 text-sm font-medium text-vermilion hover:bg-vermilion-soft"
              >
                Arrêter
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || !chatEnabled}
                className="rounded-[4px] bg-ink px-4 py-2 text-sm font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-30"
              >
                Envoyer
              </button>
            )}
          </div>
          <p className="mt-1.5 px-1 text-[11px] text-ink-faint">
            Entrée pour envoyer, Maj + Entrée pour aller à la ligne. Les réponses peuvent contenir des erreurs : les
            contrôles du panneau « Sous le capot » les signalent.
          </p>
        </form>
      </section>

      <UnderTheHood turn={selected} />
    </div>
  );
}
