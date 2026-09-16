import { CommissionLines } from "@/components/ledger/CommissionLines";
import { Stamp } from "@/components/ledger/Stamp";
import type { CommissionLineOut, ContractRecordOut, ExclusionOut } from "@/lib/api";
import { formatDate, formatEuros, summarizeArguments, TOOL_LABELS } from "@/lib/format";

import type { AssistantTurn, ToolStep } from "./types";

/** Panneau « Sous le capot » : ce que l'assistant a demandé au moteur, et ce qui a été vérifié. */
export function UnderTheHood({ turn }: { turn?: AssistantTurn }) {
  return (
    <aside
      aria-label="Sous le capot"
      className="relative flex min-h-[50vh] flex-col overflow-hidden rounded-[6px] bg-paper-deep/60 lg:h-[calc(100vh-15rem)]"
    >
      <div className="perforated shrink-0 bg-card" aria-hidden />
      <div className="flex-1 overflow-y-auto bg-card px-5 pb-8 sm:px-7">
        <header className="flex items-baseline justify-between gap-3 border-b-2 border-ink pt-3 pb-2">
          <h2 className="font-display text-3xl">Sous le capot</h2>
          {turn?.response && (
            <p className="num font-mono text-[11px] text-ink-soft">
              {turn.response.model}
              {turn.durationMs !== undefined && ` · ${(turn.durationMs / 1000).toFixed(1)} s`}
            </p>
          )}
        </header>

        {!turn ? <EmptyState /> : <TurnDetails turn={turn} />}
      </div>
    </aside>
  );
}

function EmptyState() {
  const items = [
    ["Étapes", "Chaque appel de l'assistant au moteur de calcul, avec ses paramètres."],
    ["Calculs", "Les lignes produites par le moteur : montant, règle, formule détaillée, origine du taux."],
    ["Règles", "Les règles citées, marquées d'un tampon quand le moteur les a réellement appliquées."],
    ["Contrôles", "Montants sans source, règles ou produits inventés : tout ce qui n'a pas pu être vérifié."],
  ];
  return (
    <ol className="mt-6 space-y-5">
      {items.map(([title, text], index) => (
        <li key={title} className="rise flex gap-4" style={{ animationDelay: `${index * 70}ms` }}>
          <span className="font-display text-3xl leading-none text-rule">{index + 1}</span>
          <div>
            <p className="font-medium">{title}</p>
            <p className="text-sm text-ink-soft">{text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function TurnDetails({ turn }: { turn: AssistantTurn }) {
  const response = turn.response;
  return (
    <div className="space-y-7 pt-5">
      <Section title="Étapes" count={turn.steps.length}>
        {turn.steps.length === 0 ? (
          <p className="text-sm text-ink-soft italic">
            {turn.status === "streaming"
              ? "En attente de la décision du modèle…"
              : "Aucun appel au moteur : réponse tirée des règles de référence."}
          </p>
        ) : (
          <ol className="space-y-5">
            {turn.steps.map((step, index) => (
              <StepEntry key={`${step.name}-${index}`} step={step} index={index} />
            ))}
          </ol>
        )}
      </Section>

      {response && (
        <Section title="Règles" count={response.citations.length}>
          {response.citations.length === 0 ? (
            <p className="text-sm text-ink-soft italic">Aucune règle de calcul citée.</p>
          ) : (
            <ul className="space-y-2.5">
              {response.citations.map((citation, index) => (
                <li key={citation.rule_id} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[12px] font-semibold">{citation.rule_id}</span>
                  <span className="text-sm">{citation.label}</span>
                  {citation.from_calculation ? (
                    <Stamp tone="green" delay={index * 90} title="Le moteur a appliqué cette règle dans un calcul">
                      appliquée par le moteur
                    </Stamp>
                  ) : (
                    <Stamp tone="ochre" delay={index * 90} title="Citée sans calcul du moteur à l'appui">
                      citée sans calcul
                    </Stamp>
                  )}
                  {!citation.in_answer && (
                    <span className="text-[12px] text-ink-faint">(appliquée mais non mentionnée dans la réponse)</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {response && (
        <Section title="Contrôles">
          <ul className="space-y-2">
            <Control label="Montants en euros" issues={response.unverified_amounts} issueLabel="sans source" />
            <Control label="Règles citées" issues={response.unknown_rules} issueLabel="inexistantes" />
            <Control label="Produits cités" issues={response.unknown_products} issueLabel="absents du catalogue" />
          </ul>
        </Section>
      )}

      {turn.status === "error" && (
        <Section title="Erreur">
          <p className="text-sm text-vermilion">{turn.error}</p>
        </Section>
      )}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2 font-mono text-[10.5px] tracking-[0.22em] text-ink-soft uppercase">
        {title}
        {count !== undefined && <span className="rounded-full bg-paper-deep px-1.5 text-ink">{count}</span>}
        <span className="h-px flex-1 bg-rule" aria-hidden />
      </h3>
      {children}
    </section>
  );
}

function StepEntry({ step, index }: { step: ToolStep; index: number }) {
  const facts = summarizeArguments(step.arguments);
  const result = step.trace?.result as Record<string, unknown> | undefined;
  const lines = (result?.lines as CommissionLineOut[] | undefined) ?? [];
  const exclusions = (result?.exclusions as ExclusionOut[] | undefined) ?? [];
  const isCalculation = Array.isArray(result?.lines);

  return (
    <li className="rise" style={{ animationDelay: `${index * 60}ms` }}>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[11px] text-ink-faint">{String(index + 1).padStart(2, "0")}</span>
        <p className="font-medium">{TOOL_LABELS[step.name] ?? step.name}</p>
        <span className="ml-auto font-mono text-[11px]">
          {!step.trace ? (
            <span className="text-ochre">en cours…</span>
          ) : step.trace.ok ? (
            <span className="text-green">✓</span>
          ) : (
            <span className="text-vermilion">refusé</span>
          )}
        </span>
      </div>
      {facts.length > 0 && (
        <div className="mt-1.5 ml-6 flex flex-wrap gap-1.5">
          {facts.map((fact) => (
            <span key={fact} className="rounded-[3px] bg-paper-deep px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
              {fact}
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 ml-6">
        {step.trace && !step.trace.ok && (
          <p className="text-[13px] text-vermilion">{String(result?.error ?? "Erreur")}</p>
        )}
        {step.trace?.ok && Array.isArray(result?.current_records) && <ContractHistory result={result} />}
        {step.trace?.ok && isCalculation && <CommissionLines lines={lines} exclusions={exclusions} compact />}
        {step.trace?.ok && typeof result?.key_strategy_label === "string" && <PerimeterSummary result={result} />}
      </div>
    </li>
  );
}

function ContractHistory({ result }: { result: Record<string, unknown> }) {
  const rows: [string, ContractRecordOut[]][] = [
    [String(result.previous_month), result.previous_records as ContractRecordOut[]],
    [String(result.month), result.current_records as ContractRecordOut[]],
  ];
  return (
    <table className="num mb-3 w-full font-mono text-[11.5px]">
      <thead>
        <tr className="text-left text-ink-faint">
          <th className="pb-1 font-normal">Mois</th>
          <th className="pb-1 font-normal">État</th>
          <th className="pb-1 font-normal">Effet</th>
          <th className="pb-1 font-normal">Fin</th>
          <th className="pb-1 text-right font-normal">Prime</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([month, records]) =>
          records.length === 0 ? (
            <tr key={month} className="border-t border-rule">
              <td className="py-1">{month}</td>
              <td colSpan={4} className="py-1 text-ink-faint">
                absent du bordereau
              </td>
            </tr>
          ) : (
            records.map((record, i) => (
              <tr key={`${month}-${i}`} className="border-t border-rule">
                <td className="py-1">{month}</td>
                <td className="py-1">{record.state}</td>
                <td className="py-1">{formatDate(record.effective_date)}</td>
                <td className="py-1">{formatDate(record.end_date)}</td>
                <td className="py-1 text-right">{formatEuros(record.annual_premium)}</td>
              </tr>
            ))
          ),
        )}
      </tbody>
    </table>
  );
}

function PerimeterSummary({ result }: { result: Record<string, unknown> }) {
  const products = (result.products as { code: string; label: string; year_1: { display: string }[] }[]) ?? [];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
      <dt className="text-ink-faint">Périmètre</dt>
      <dd>{String(result.label)}</dd>
      <dt className="text-ink-faint">Rapprochement</dt>
      <dd>{String(result.key_strategy_label)}</dd>
      <dt className="text-ink-faint">Exposition</dt>
      <dd>{String(result.exposure_base_label)}</dd>
      <dt className="text-ink-faint">Produits</dt>
      <dd>
        {products.map((product) => (
          <span key={product.code} className="mr-3 inline-block">
            {product.label}{" "}
            <span className="num font-mono text-ink-soft">{product.year_1.map((w) => w.display).join(" → ")}</span>
          </span>
        ))}
      </dd>
    </dl>
  );
}

function Control({ label, issues, issueLabel }: { label: string; issues: string[]; issueLabel: string }) {
  const ok = issues.length === 0;
  return (
    <li className="flex flex-wrap items-center gap-2 text-sm">
      <span className={ok ? "text-green" : "text-vermilion"} aria-hidden>
        {ok ? "✓" : "⚠"}
      </span>
      <span>{label}</span>
      {ok ? (
        <span className="text-ink-faint">tous vérifiés</span>
      ) : (
        <>
          <Stamp tone="vermilion">
            {issues.length} {issueLabel}
          </Stamp>
          <span className="num font-mono text-[12px] text-vermilion">{issues.join(" · ")}</span>
        </>
      )}
    </li>
  );
}
