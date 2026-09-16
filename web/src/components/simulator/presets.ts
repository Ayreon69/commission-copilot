export type ContractState = "AFN" | "SEF" | "RES";

export type SimulationForm = {
  perimeter: string;
  product: string;
  month: string;
  state: ContractState;
  subscriptionDate: string;
  effectiveDate: string;
  endDate: string;
  annualPremium: string;
  segment: string;
  guarantee: string;
  hadPreviousMonth: boolean;
  previousState: ContractState;
  previousPremium: string;
};

const BASE: SimulationForm = {
  perimeter: "SANTE_INDIV",
  product: "NS-CONFORT",
  month: "2026-03",
  state: "AFN",
  subscriptionDate: "2026-02-20",
  effectiveDate: "2026-03-01",
  endDate: "",
  annualPremium: "1500",
  segment: "",
  guarantee: "",
  hadPreviousMonth: false,
  previousState: "AFN",
  previousPremium: "",
};

export const DEFAULT_FORM = BASE;

export const PRESETS: { id: string; title: string; hint: string; form: SimulationForm }[] = [
  {
    id: "nouvelle-affaire",
    title: "Nouvelle affaire",
    hint: "Précompte versé d'avance",
    form: BASE,
  },
  {
    id: "sans-effet",
    title: "Sans effet",
    hint: "Reprise totale",
    form: {
      ...BASE,
      product: "NS-ESSENTIEL",
      state: "SEF",
      subscriptionDate: "2026-01-15",
      effectiveDate: "2026-02-01",
      annualPremium: "1000",
      hadPreviousMonth: true,
    },
  },
  {
    id: "resiliation",
    title: "Résiliation",
    hint: "Reprise au prorata",
    form: {
      ...BASE,
      perimeter: "ANIMAUX",
      product: "VA-COMPAGNON",
      state: "RES",
      subscriptionDate: "2025-10-20",
      effectiveDate: "2025-11-01",
      endDate: "2026-03-31",
      annualPremium: "480",
      hadPreviousMonth: true,
    },
  },
  {
    id: "hausse-prime",
    title: "Hausse de prime",
    hint: "Régularisation",
    form: {
      ...BASE,
      subscriptionDate: "2026-01-10",
      effectiveDate: "2026-02-01",
      annualPremium: "1320",
      hadPreviousMonth: true,
      previousPremium: "1200",
    },
  },
  {
    id: "taux-negocie",
    title: "Taux négocié",
    hint: "Segment rachat de crédit",
    form: {
      ...BASE,
      perimeter: "EMPRUNTEUR",
      product: "NE-EMPRUNT-CLASSIQUE",
      subscriptionDate: "2026-02-25",
      annualPremium: "800",
      segment: "RACHAT",
    },
  },
  {
    id: "contrat-ancien",
    title: "Contrat ancien",
    hint: "Précompte déjà acquis",
    form: { ...BASE, subscriptionDate: "2024-11-20", effectiveDate: "2024-12-01" },
  },
];
