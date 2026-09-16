export type Tone = "green" | "vermilion" | "ink";

export const COMMISSION_LABELS: Record<string, string> = {
  P: "Précompte",
  RP: "Reprise",
  L: "Linéaire",
};

export const STATE_LABELS: Record<string, string> = {
  AFN: "Actif",
  SEF: "Sans effet",
  RES: "Résilié",
};

export const TOOL_LABELS: Record<string, string> = {
  get_perimeter_details: "Paramétrage du périmètre",
  simulate_contract: "Simulation par le moteur",
  lookup_sample_contract: "Consultation du contrat",
};

export function toneOf(value: string | number): Tone {
  const amount = Number(value);
  if (amount > 0) return "green";
  if (amount < 0) return "vermilion";
  return "ink";
}

export const TONE_TEXT: Record<Tone, string> = {
  green: "text-green",
  vermilion: "text-vermilion",
  ink: "text-ink",
};

const monthFormatter = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" });
const euroFormatter = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });

/** "2026-03-15" -> "15/03/2026", sans passer par un fuseau horaire. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [year, month, day] = iso.split("-");
  return `${day}/${month}/${year}`;
}

/** "2026-03" -> "mars 2026" */
export function formatMonth(month: string): string {
  const [year, index] = month.split("-").map(Number);
  return monthFormatter.format(new Date(Date.UTC(year, index - 1, 1)));
}

export function formatEuros(value: string | number): string {
  return euroFormatter.format(Number(value));
}

/** Faits marquants des arguments d'un appel d'outil, à afficher en étiquettes. */
export function summarizeArguments(args: Record<string, unknown>): string[] {
  const facts: string[] = [];
  const contract = (args.contract ?? {}) as Record<string, unknown>;
  const previous = args.previous_month as Record<string, unknown> | undefined;
  const push = (value: unknown, render: (v: string) => string = (v) => v) => {
    if (value !== undefined && value !== null && value !== "") facts.push(render(String(value)));
  };
  push(args.perimeter);
  push(args.contract_id);
  push(contract.product);
  push(contract.state, (v) => STATE_LABELS[v] ?? v);
  push(contract.annual_premium, (v) => `prime ${formatEuros(v)}`);
  push(contract.segment, (v) => `segment ${v}`);
  push(contract.end_date, (v) => `fin ${formatDate(v)}`);
  if (previous) push(previous.state, (v) => `mois précédent : ${(STATE_LABELS[v] ?? v).toLowerCase()}`);
  push(args.month, formatMonth);
  return facts;
}
