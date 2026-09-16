"use client";

import { useEffect, useState } from "react";

import { CommissionLines } from "@/components/ledger/CommissionLines";
import {
  api,
  ApiError,
  type CalculationOut,
  type PerimeterDetailsOut,
  type PerimeterSummaryOut,
  type SimulationRequest,
} from "@/lib/api";
import { formatDate, formatEuros, formatMonth, STATE_LABELS, TONE_TEXT, toneOf } from "@/lib/format";

import { ContractTimeline } from "./ContractTimeline";
import { type ContractState, DEFAULT_FORM, PRESETS, type SimulationForm } from "./presets";

type Result = { state: "idle" } | { state: "loading" } | { state: "error"; message: string } | { state: "done"; calculation: CalculationOut; form: SimulationForm };

type SimulatorViewProps = {
  onAskAssistant: (question: string) => void;
};

export function SimulatorView({ onAskAssistant }: SimulatorViewProps) {
  const [perimeters, setPerimeters] = useState<PerimeterSummaryOut[]>([]);
  const [details, setDetails] = useState<Record<string, PerimeterDetailsOut>>({});
  const [form, setForm] = useState<SimulationForm>(DEFAULT_FORM);
  const [presetId, setPresetId] = useState<string | null>(PRESETS[0].id);
  const [result, setResult] = useState<Result>({ state: "idle" });
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    api
      .perimeters()
      .then((items) => setPerimeters(items.filter((item) => item.active)))
      .catch((error: Error) => setCatalogError(error.message));
  }, []);

  useEffect(() => {
    if (!form.perimeter || details[form.perimeter]) return;
    api
      .perimeter(form.perimeter)
      .then((detail) => setDetails((current) => ({ ...current, [detail.code]: detail })))
      .catch((error: Error) => setCatalogError(error.message));
  }, [form.perimeter, details]);

  const detail = details[form.perimeter];
  const segments = detail?.rate_overrides.filter((override) => override.segment) ?? [];
  const guarantees = detail?.rate_overrides.filter((override) => override.guarantee) ?? [];

  const update = (change: Partial<SimulationForm>) => {
    setPresetId(null);
    setForm((current) => ({ ...current, ...change }));
  };

  const run = async (values: SimulationForm) => {
    setResult({ state: "loading" });
    try {
      const calculation = await api.simulate(toRequest(values));
      setResult({ state: "done", calculation, form: values });
    } catch (error) {
      setResult({ state: "error", message: error instanceof ApiError ? error.message : String(error) });
    }
  };

  const applyPreset = (id: string) => {
    const preset = PRESETS.find((item) => item.id === id);
    if (!preset) return;
    setPresetId(id);
    setForm(preset.form);
    void run(preset.form);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section aria-label="Paramètres du contrat" className="rounded-[6px] border border-rule bg-card/80 p-5 sm:p-7">
        <h2 className="font-display text-3xl">Chiffrer un contrat</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Le simulateur appelle directement le moteur de calcul, sans modèle de langage : même moteur, mêmes règles
          que l&apos;assistant.
        </p>

        <div className="mt-5">
          <p className="mb-2 font-mono text-[10.5px] tracking-[0.2em] text-ink-faint uppercase">Cas types</p>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset.id)}
                aria-pressed={presetId === preset.id}
                className={`rounded-[4px] border px-3 py-1.5 text-left transition focus-visible:ring-2 focus-visible:ring-ochre focus-visible:outline-none ${
                  presetId === preset.id ? "border-ink bg-ink text-paper" : "border-rule hover:border-ink"
                }`}
              >
                <span className="block text-[13px] font-medium">{preset.title}</span>
                <span className={`block text-[11px] ${presetId === preset.id ? "text-paper/70" : "text-ink-faint"}`}>
                  {preset.hint}
                </span>
              </button>
            ))}
          </div>
        </div>

        {catalogError && <p className="mt-4 text-sm text-vermilion">{catalogError}</p>}

        <form
          className="mt-6 grid gap-x-4 gap-y-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            void run(form);
          }}
        >
          <Field label="Périmètre">
            <select
              value={form.perimeter}
              onChange={(event) => update({ perimeter: event.target.value, product: "", segment: "", guarantee: "" })}
              className={INPUT}
            >
              {perimeters.length === 0 && <option value={form.perimeter}>{form.perimeter}</option>}
              {perimeters.map((perimeter) => (
                <option key={perimeter.code} value={perimeter.code}>
                  {perimeter.label} · {perimeter.insurer}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Produit">
            <select value={form.product} onChange={(event) => update({ product: event.target.value })} className={INPUT} required>
              <option value="" disabled>
                Choisir un produit
              </option>
              {(detail?.products ?? []).map((product) => (
                <option key={product.code} value={product.code}>
                  {product.label}
                </option>
              ))}
              {!detail && form.product && <option value={form.product}>{form.product}</option>}
            </select>
          </Field>

          <Field label="Mois de calcul">
            <input type="month" value={form.month} onChange={(event) => update({ month: event.target.value })} className={INPUT} required />
          </Field>

          <Field label="Prime annuelle HT (€)">
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={form.annualPremium}
              onChange={(event) => update({ annualPremium: event.target.value })}
              className={`${INPUT} num font-mono`}
              required
            />
          </Field>

          <Field label="Souscription">
            <input type="date" value={form.subscriptionDate} onChange={(event) => update({ subscriptionDate: event.target.value })} className={INPUT} required />
          </Field>

          <Field label="Effet">
            <input type="date" value={form.effectiveDate} onChange={(event) => update({ effectiveDate: event.target.value })} className={INPUT} required />
          </Field>

          <Field label="État ce mois-ci" wide>
            <StateToggle value={form.state} onChange={(state) => update({ state, endDate: state === "RES" ? form.endDate : "" })} />
          </Field>

          {form.state === "RES" && (
            <Field label="Date de résiliation">
              <input type="date" value={form.endDate} onChange={(event) => update({ endDate: event.target.value })} className={INPUT} required />
            </Field>
          )}

          {segments.length > 0 && (
            <Field label="Segment à taux négocié">
              <select value={form.segment} onChange={(event) => update({ segment: event.target.value })} className={INPUT}>
                <option value="">Aucun</option>
                {segments.map((override) => (
                  <option key={override.segment} value={override.segment ?? ""}>
                    {override.segment} — {override.display}
                  </option>
                ))}
              </select>
            </Field>
          )}

          {guarantees.length > 0 && (
            <Field label="Garantie à taux spécifique">
              <select value={form.guarantee} onChange={(event) => update({ guarantee: event.target.value })} className={INPUT}>
                <option value="">Aucune</option>
                {guarantees.map((override) => (
                  <option key={override.guarantee} value={override.guarantee ?? ""}>
                    {override.guarantee} — {override.display}
                  </option>
                ))}
              </select>
            </Field>
          )}

          <fieldset className="rounded-[5px] border border-dashed border-rule p-3 sm:col-span-2">
            <legend className="px-1 text-[13px] font-medium">Mois précédent</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.hadPreviousMonth}
                onChange={(event) => update({ hadPreviousMonth: event.target.checked })}
                className="h-4 w-4 accent-[var(--ink)]"
              />
              Le contrat figurait déjà au bordereau du mois précédent
            </label>
            {form.hadPreviousMonth && (
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <Field label="État le mois précédent">
                  <StateToggle value={form.previousState} onChange={(previousState) => update({ previousState })} />
                </Field>
                <Field label="Prime le mois précédent (si différente)">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.previousPremium}
                    placeholder="identique"
                    onChange={(event) => update({ previousPremium: event.target.value })}
                    className={`${INPUT} num font-mono`}
                  />
                </Field>
              </div>
            )}
          </fieldset>

          <div className="sm:col-span-2">
            <ContractTimeline
              subscriptionDate={form.subscriptionDate}
              effectiveDate={form.effectiveDate}
              endDate={form.state === "RES" ? form.endDate : ""}
              month={form.month}
            />
          </div>

          <button
            type="submit"
            disabled={result.state === "loading"}
            className="rounded-[4px] bg-ink px-5 py-2.5 text-sm font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-40 sm:col-span-2 sm:justify-self-start"
          >
            {result.state === "loading" ? "Calcul en cours…" : "Calculer avec le moteur"}
          </button>
        </form>
      </section>

      <Receipt result={result} perimeters={perimeters} details={details} onAskAssistant={onAskAssistant} />
    </div>
  );
}

const INPUT =
  "w-full rounded-[4px] border border-rule bg-paper/60 px-2.5 py-2 text-sm text-ink focus:border-ink focus:ring-2 focus:ring-ochre/40 focus:outline-none";

function Field({ label, children, wide = false }: { label: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <label className={`block ${wide ? "sm:col-span-2" : ""}`}>
      <span className="mb-1 block text-[12px] font-medium text-ink-soft">{label}</span>
      {children}
    </label>
  );
}

function StateToggle({ value, onChange }: { value: ContractState; onChange: (state: ContractState) => void }) {
  return (
    <div role="radiogroup" className="flex rounded-[4px] border border-rule bg-paper/60 p-0.5">
      {(Object.keys(STATE_LABELS) as ContractState[]).map((state) => (
        <button
          key={state}
          type="button"
          role="radio"
          aria-checked={value === state}
          onClick={() => onChange(state)}
          className={`flex-1 rounded-[3px] px-2 py-1.5 text-[13px] transition-colors ${
            value === state ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
          }`}
        >
          {STATE_LABELS[state]} <span className="font-mono text-[10px] opacity-60">{state}</span>
        </button>
      ))}
    </div>
  );
}

function toRequest(form: SimulationForm): SimulationRequest {
  return {
    perimeter: form.perimeter,
    month: form.month,
    contract: {
      product: form.product,
      state: form.state,
      subscription_date: form.subscriptionDate,
      effective_date: form.effectiveDate,
      annual_premium: form.annualPremium,
      end_date: form.state === "RES" && form.endDate ? form.endDate : null,
      segment: form.segment,
      guarantee: form.guarantee,
    },
    previous_month: form.hadPreviousMonth
      ? { state: form.previousState, annual_premium: form.previousPremium || null }
      : null,
  };
}

function Receipt({
  result,
  perimeters,
  details,
  onAskAssistant,
}: {
  result: Result;
  perimeters: PerimeterSummaryOut[];
  details: Record<string, PerimeterDetailsOut>;
  onAskAssistant: (question: string) => void;
}) {
  return (
    <aside aria-label="Résultat du moteur" aria-live="polite" className="lg:sticky lg:top-6 lg:self-start">
      <div className="perforated bg-card" aria-hidden />
      <div className="min-h-[420px] bg-card px-6 pb-8 shadow-[0_18px_40px_-28px_rgba(28,26,21,0.4)] sm:px-8">
        {result.state === "idle" && (
          <div className="pt-10 text-center">
            <p className="font-display text-3xl text-ink-soft">Bordereau vierge</p>
            <p className="mt-2 text-sm text-ink-faint">Choisissez un cas type ou renseignez le contrat, puis lancez le calcul.</p>
          </div>
        )}
        {result.state === "loading" && <p className="scanning pt-10 text-center font-mono text-sm text-ink-soft">Le moteur calcule…</p>}
        {result.state === "error" && (
          <div className="pt-8">
            <p className="font-display text-2xl text-vermilion">Calcul refusé</p>
            <p className="mt-2 text-sm">{result.message}</p>
          </div>
        )}
        {result.state === "done" && (
          <DoneReceipt
            calculation={result.calculation}
            form={result.form}
            perimeterLabel={perimeters.find((p) => p.code === result.calculation.perimeter)?.label ?? result.calculation.perimeter}
            productLabel={details[result.form.perimeter]?.products.find((p) => p.code === result.form.product)?.label ?? result.form.product}
            onAskAssistant={onAskAssistant}
          />
        )}
      </div>
      <div className="perforated rotate-180 bg-card" aria-hidden />
    </aside>
  );
}

function DoneReceipt({
  calculation,
  form,
  perimeterLabel,
  productLabel,
  onAskAssistant,
}: {
  calculation: CalculationOut;
  form: SimulationForm;
  perimeterLabel: string;
  productLabel: string;
  onAskAssistant: (question: string) => void;
}) {
  const net = calculation.totals.net;
  const question = buildQuestion(form, productLabel, calculation.month);
  return (
    <div key={JSON.stringify(calculation)} className="pt-4">
      <header className="flex items-baseline justify-between border-b-2 border-ink pb-2">
        <p className="font-mono text-[10.5px] tracking-[0.2em] text-ink-soft uppercase">
          Bordereau · {perimeterLabel} · {formatMonth(calculation.month)}
        </p>
      </header>

      <div className="rise py-6">
        <p className="text-sm text-ink-soft">{productLabel}</p>
        <p className={`num font-mono text-5xl font-semibold tracking-tight sm:text-6xl ${TONE_TEXT[toneOf(net.value)]}`}>{net.display}</p>
        <p className="mt-1 text-sm text-ink-soft">
          {calculation.lines.length === 0
            ? "Aucune commission ce mois-ci."
            : Number(net.value) < 0
              ? "À rembourser à l'assureur."
              : "Commission due au cabinet."}
        </p>
      </div>

      <CommissionLines lines={calculation.lines} exclusions={calculation.exclusions} />

      <dl className="num mt-6 grid grid-cols-3 gap-2 border-t border-dashed border-rule pt-3 font-mono text-[11.5px]">
        {(
          [
            ["Précompte", calculation.totals.precompte],
            ["Reprises", calculation.totals.reprises],
            ["Linéaire", calculation.totals.lineaire],
          ] as const
        ).map(([label, amount]) => (
          <div key={label}>
            <dt className="text-ink-faint">{label}</dt>
            <dd className={TONE_TEXT[toneOf(amount.value)]}>{amount.display}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        onClick={() => onAskAssistant(question)}
        className="mt-6 w-full rounded-[4px] border border-ink px-4 py-2.5 text-sm font-medium transition hover:bg-ink hover:text-paper"
      >
        Demander à l&apos;assistant d&apos;expliquer ce résultat →
      </button>
    </div>
  );
}

function buildQuestion(form: SimulationForm, productLabel: string, month: string): string {
  const parts = [
    `Contrat ${productLabel}, prime annuelle de ${formatEuros(form.annualPremium)}, souscrit le ${formatDate(form.subscriptionDate)}, effet au ${formatDate(form.effectiveDate)}`,
  ];
  if (form.segment) parts.push(`segment ${form.segment}`);
  if (form.hadPreviousMonth) {
    const previous = STATE_LABELS[form.previousState].toLowerCase();
    parts.push(
      `${previous} le mois précédent${form.previousPremium ? ` avec une prime de ${formatEuros(form.previousPremium)}` : ""}`,
    );
  }
  const current =
    form.state === "RES"
      ? `résilié au ${formatDate(form.endDate)}`
      : STATE_LABELS[form.state].toLowerCase();
  parts.push(`${current} en ${formatMonth(month)}`);
  return `${parts.join(", ")}. Explique-moi la commission calculée pour ce mois.`;
}
