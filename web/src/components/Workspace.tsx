"use client";

import { useEffect, useState } from "react";

import { AssistantView } from "@/components/assistant/AssistantView";
import { SimulatorView } from "@/components/simulator/SimulatorView";
import { api, type HealthOut } from "@/lib/api";

type Tab = "assistant" | "simulator";
type Health = { state: "loading" } | { state: "offline" } | { state: "online"; health: HealthOut };

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "assistant", label: "Assistant", hint: "Poser une question" },
  { id: "simulator", label: "Simulateur", hint: "Chiffrer un contrat" },
];

export function Workspace() {
  const [tab, setTab] = useState<Tab>("assistant");
  const [health, setHealth] = useState<Health>({ state: "loading" });
  const [draftQuestion, setDraftQuestion] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((result) => setHealth({ state: "online", health: result }))
      .catch(() => setHealth({ state: "offline" }));
  }, []);

  const askAssistant = (question: string) => {
    setDraftQuestion(question);
    setTab("assistant");
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-[1440px] flex-col px-4 sm:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-ink pt-6 pb-4">
        <div className="rise">
          <p className="font-mono text-[10.5px] tracking-[0.22em] text-ink-soft uppercase">
            Opaline Courtage · bordereau n° 2026-03
          </p>
          <h1 className="font-display text-[2.6rem] leading-none tracking-tight sm:text-5xl">
            Commission <em className="text-vermilion">Copilot</em>
          </h1>
          <p className="mt-1.5 max-w-xl text-sm text-ink-soft">
            Le modèle de langage explique, le moteur calcule. Chaque montant affiché sort du moteur, chaque règle
            citée est vérifiée.
          </p>
        </div>
        <div className="rise flex flex-col items-end gap-3" style={{ animationDelay: "120ms" }}>
          <HealthBadge health={health} />
          <nav aria-label="Vues" className="flex rounded-[4px] border border-ink bg-card p-0.5">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                aria-pressed={tab === item.id}
                title={item.hint}
                className={`rounded-[3px] px-4 py-1.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ochre focus-visible:outline-none ${
                  tab === item.id ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 py-6">
        <div hidden={tab !== "assistant"} className="h-full">
          <AssistantView
            chatEnabled={health.state === "online" ? health.health.chat_enabled : true}
            draftQuestion={draftQuestion}
            onDraftConsumed={() => setDraftQuestion(null)}
          />
        </div>
        <div hidden={tab !== "simulator"}>
          <SimulatorView onAskAssistant={askAssistant} />
        </div>
      </main>

      <footer className="flex flex-wrap justify-between gap-2 border-t border-rule py-4 font-mono text-[10.5px] tracking-wider text-ink-faint uppercase">
        <span>Données 100 % fictives · Opaline Courtage, Nordale, Verdance et Calvane n&apos;existent pas</span>
        <span>Moteur déterministe · LLM avec appels d&apos;outils · contrôles a posteriori</span>
      </footer>
    </div>
  );
}

function HealthBadge({ health }: { health: Health }) {
  if (health.state === "loading") {
    return <span className="font-mono text-[11px] text-ink-faint">Connexion à l&apos;API…</span>;
  }
  if (health.state === "offline") {
    return (
      <span className="rounded-full border border-vermilion px-2.5 py-0.5 font-mono text-[11px] text-vermilion">
        ● API hors ligne
      </span>
    );
  }
  const { chat_enabled, model } = health.health;
  return chat_enabled ? (
    <span className="rounded-full border border-green px-2.5 py-0.5 font-mono text-[11px] text-green">
      ● {model}
    </span>
  ) : (
    <span className="rounded-full border border-ochre px-2.5 py-0.5 font-mono text-[11px] text-ochre">
      ● Assistant désactivé : clé LLM_API_KEY absente
    </span>
  );
}
