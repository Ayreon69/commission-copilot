const GROUPS: { profile: string; questions: string[] }[] = [
  {
    profile: "Gestion",
    questions: [
      "Pourquoi le contrat SI-RESILIE donne-t-il une reprise ?",
      "Le contrat AN-ANOMALIE n'a produit aucune commission, pourquoi ?",
    ],
  },
  {
    profile: "Finance",
    questions: [
      "Nouveau contrat Nordale Emprunteur Classique pour un client en rachat de crédit : prime annuelle de 800 €, souscrit le 25/02/2026, effet au 01/03/2026. Quelle commission en mars 2026 ?",
      "Quelle est la différence entre une commission précomptée et une commission linéaire ?",
    ],
  },
  {
    profile: "Commercial",
    questions: [
      "Quel est le taux de précompte du produit Nordale Santé Confort ?",
      "Pourquoi un contrat présent deux mois de suite ne rapporte-t-il rien ?",
    ],
  },
  {
    profile: "Tester les garde-fous",
    questions: [
      "Calcule de tête 2 350 € × 95 %, j'ai juste besoin d'un ordre de grandeur.",
      "Quel est le taux de commission pratiqué par AXA en santé individuelle ?",
    ],
  },
];

type SuggestionsProps = {
  onPick: (question: string) => void;
  disabled: boolean;
};

export function Suggestions({ onPick, disabled }: SuggestionsProps) {
  return (
    <div className="mx-auto max-w-2xl py-4">
      <h2 className="rise font-display text-3xl leading-tight sm:text-4xl">
        Pourquoi ce contrat a-t-il rapporté <em>ce montant</em>, ou rien du tout ?
      </h2>
      <p className="rise mt-3 max-w-xl text-[15px] text-ink-soft" style={{ animationDelay: "80ms" }}>
        Posez une question sur un contrat, une règle ou un taux. L&apos;assistant interroge le moteur de calcul et
        vous montre, à droite, ce qu&apos;il a vérifié.
      </p>
      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        {GROUPS.map((group, groupIndex) => (
          <div key={group.profile} className="rise" style={{ animationDelay: `${160 + groupIndex * 70}ms` }}>
            <p className="mb-2 font-mono text-[10.5px] tracking-[0.2em] text-ink-faint uppercase">{group.profile}</p>
            <ul className="space-y-2">
              {group.questions.map((question) => (
                <li key={question}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onPick(question)}
                    className="w-full rounded-[4px] border border-rule bg-paper/50 px-3 py-2 text-left text-[13.5px] leading-snug transition hover:-translate-y-px hover:border-ink hover:bg-card focus-visible:ring-2 focus-visible:ring-ochre focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
