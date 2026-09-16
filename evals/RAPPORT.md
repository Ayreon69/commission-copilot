# Évaluation de l'assistant

Rapport généré par `python -m evals.run`. Chaque modèle répond seul (sans modèle de secours) au jeu de questions de [dataset.yaml](dataset.yaml). Les vérifications sont déterministes, sans modèle juge : outils appelés, montants exacts, règles citées, termes attendus, montants interdits, et aucun montant sans source.

## Synthèse

| Modèle | Questions réussies | Vérifications | Montants sans source | Produits ou règles inexistants | Erreurs d'infrastructure | Latence médiane | Appels au modèle | Date |
|---|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 93 % (25/27) | 99 % (155/157) | 0 | 0 | 0 | 1.9 s | 48 | 2026-09-16 |
| `gemini-3.7-flash (incomplet)` | — | — | 0 | 0 | 3 | — | 12 | 2026-09-16 |

## Par catégorie

| Catégorie | `gemini-3.5-flash-lite` | `gemini-3.7-flash` |
|---|---|---|
| Explication d'un contrat | 89 % (8/9) | — |
| Simulation d'un cas | 100 % (6/6) | — |
| Règles et paramétrage | 100 % (5/5) | — |
| Informations manquantes | 100 % (2/2) | — |
| Limites et pièges | 75 % (3/4) | — |
| Suivi de conversation | 100 % (1/1) | — |

## Questions échouées

### `gemini-3.5-flash-lite`

- **contrat-taux-negocie** : mentionne « 30 % » ou « 30% »
- **assureur-reel** : mentionne « fictif » ou « ne dispose pas » ou « pas d'information » ou « pas acces » ou « uniquement » ou « ne connais pas »

### `gemini-3.7-flash`

- **contrat-resilie** : erreur d'infrastructure (gemini-3.7-flash : indisponible)
- **contrat-sans-effet** : erreur d'infrastructure (gemini-3.7-flash : indisponible)
- **contrat-stable** : erreur d'infrastructure (gemini-3.7-flash : quota atteint)
