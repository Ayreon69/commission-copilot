import type { CommissionLineOut, ExclusionOut } from "@/lib/api";
import { COMMISSION_LABELS, TONE_TEXT, toneOf } from "@/lib/format";

type CommissionLinesProps = {
  lines: CommissionLineOut[];
  exclusions: ExclusionOut[];
  compact?: boolean;
};

/** Lignes calculées par le moteur et motifs d'exclusion, présentés comme les lignes d'un bordereau. */
export function CommissionLines({ lines, exclusions, compact = false }: CommissionLinesProps) {
  if (!lines.length && !exclusions.length) {
    return <p className="text-sm text-ink-faint italic">Aucun mouvement pour ce contrat.</p>;
  }
  return (
    <div className="space-y-3">
      {lines.map((line, index) => (
        <article
          key={`${line.contract_id}-${line.rule_id}-${index}`}
          className="rise border-l-2 pl-3"
          style={{ animationDelay: `${index * 60}ms`, borderColor: `var(--${toneOf(line.amount)})` }}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="text-[13px] text-ink-soft">
              <span className="font-mono text-[11px] font-semibold tracking-wider text-ink">
                {COMMISSION_LABELS[line.commission_type] ?? line.commission_type}
              </span>
              <span className="mx-1.5 text-rule">/</span>
              {line.rule_label} <span className="font-mono text-[11px] text-ink-faint">{line.rule_id}</span>
            </p>
            <p className={`num font-mono font-semibold ${compact ? "text-base" : "text-lg"} ${TONE_TEXT[toneOf(line.amount)]}`}>
              {line.amount_display}
            </p>
          </div>
          <p className="num mt-1 font-mono text-[12px] leading-relaxed text-ink [overflow-wrap:anywhere]">

            {line.formula}
          </p>
          {!compact && <p className="mt-0.5 text-[12px] text-ink-faint">Taux : {line.rate_source}</p>}
        </article>
      ))}
      {exclusions.length > 0 && (
        <ul className="space-y-1.5">
          {exclusions.map((exclusion, index) => (
            <li key={`${exclusion.contract_id}-${exclusion.code}-${index}`} className="flex gap-2 text-[13px]">
              <span aria-hidden className="text-ochre">
                ⊘
              </span>
              <span>
                <span className="font-medium text-ink">{exclusion.label}</span>
                {exclusion.detail && <span className="text-ink-soft"> — {exclusion.detail}</span>}
                <span className="ml-1.5 font-mono text-[10.5px] text-ink-faint">{exclusion.code}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
