# Commission Copilot

Assistant pour comprendre la rémunération d'un cabinet de courtage en assurance. Il combine **un moteur de calcul
déterministe**, qui chiffre les commissions, et **un assistant conversationnel**, qui explique les règles et
fait appel au moteur dès qu'il faut un chiffre.

> Toutes les données sont fictives : cabinet, assureurs, produits, taux et contrats. Voir [docs/DONNEES_FICTIVES.md](docs/DONNEES_FICTIVES.md).

## Le problème

Dans un cabinet de courtage, la commission d'un contrat dépend de dizaines de règles : précompte versé d'avance,
reprise si le contrat s'arrête trop tôt, commission linéaire les années suivantes, grilles de taux datées, exceptions
propres à chaque assureur… Les équipes finance, gestion et commerciales ne peuvent pas lire le code qui applique ces
règles. Pour savoir *pourquoi* un contrat a rapporté tel montant, ou rien du tout, elles dépendent des développeurs.

## Le principe : le LLM explique, le moteur calcule

Un modèle de langage peut inventer un taux avec autant d'assurance qu'il cite une règle exacte. Sur un montant de
commission, l'erreur coûte cher et passe inaperçue. Ce projet sépare donc strictement les rôles :

| Composant | Rôle | Garantie |
|---|---|---|
| **Moteur** (`engine/`) | Calcule chaque commission et justifie chaque exclusion | Déterministe et testé ; chaque ligne porte sa règle et sa formule |
| **Assistant** (`api/`) | Explique les règles et appelle le moteur pour tout chiffrage | Tout montant cité est comparé aux résultats des outils ; un montant sans source est signalé |

Exemple de ligne produite par le moteur :

```text
RP  SI-RESILIE   −1 044,50 €  [R-RP2] (2 089,00 € × 120 % × 7/12) − (2 089,00 € × 120 %) = 1 462,30 € − 2 506,80 € = −1 044,50 €
```

Pour répondre à « Pourquoi le contrat SI-RESILIE donne-t-il une reprise ? », l'assistant appelle l'outil
`lookup_sample_contract`, reçoit l'historique du contrat et le calcul du moteur, puis l'explique en langage métier.
La réponse de l'API contient la trace de chaque appel d'outil et la liste des montants non vérifiés.

L'architecture et ses garde-fous sont détaillés dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Fiabilité mesurée

L'assistant est évalué sur 27 questions de référence, réparties en six catégories : explication d'un contrat,
simulation, règles, informations manquantes, pièges et suivi de conversation. Les vérifications sont déterministes :
outils appelés, montants exacts, règles citées, montants interdits. Les réponses attendues sont recalculées par le
moteur dans les tests. Détail dans [evals/RAPPORT.md](evals/RAPPORT.md).

| Modèle (plan gratuit Gemini) | Questions réussies | Montants sans source | Latence médiane |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 85 % (23/27) | 0 | 1,9 s |
| `gemini-3.7-flash` | non évaluable : surcharges répétées puis quota journalier épuisé | — | — |

**Ce que l'évaluation a permis de corriger.** Pour un client en rachat de crédit, le modèle transmettait le segment
`RACHAT_CREDIT` au lieu de `RACHAT`. Le taux négocié ne s'appliquait pas, et l'assistant annonçait 280 € au lieu de
336 € en justifiant le mauvais taux. Le contrôle des montants ne pouvait pas le voir : le chiffre venait bien du
moteur, mais calculé sur une mauvaise donnée. Désormais, les segments autorisés sont imposés dans la définition de
l'outil, et le service refuse tout segment inconnu. Le cas est réussi depuis.

**Limites connues.**
- Les scores varient d'une exécution à l'autre : deux passages ont donné 24 puis 23 questions réussies, sans échouer
  sur les mêmes questions.
- Les vérifications par mots-clés peuvent rejeter une réponse correcte formulée autrement.
- Les échecs restants sont surtout des réponses incomplètes, par exemple une explication de taux qui ne cite pas le
  pourcentage.

## Structure

```text
commission-copilot/
├── engine/                     Moteur de calcul Python, sans dépendance externe
│   ├── commission_engine/      Préparation, rapprochement M/M-1, précompte, linéaire
│   ├── scripts/                Génération des bordereaux d'exemple
│   └── tests/
├── api/                        API FastAPI et assistant
│   ├── commission_api/
│   │   ├── services.py         Cas d'usage partagés par les routes et les outils
│   │   ├── routes.py           Points d'entrée HTTP
│   │   └── assistant/          Boucle d'outils, définitions d'outils, prompt, contrôle des montants
│   └── tests/                  Tests avec un modèle de langage scripté (aucun appel réseau)
├── evals/                      Évaluation de l'assistant
│   ├── dataset.yaml            27 questions de référence et leurs vérifications
│   ├── run.py, report.py       Exécution par modèle et rapport comparatif
│   └── RAPPORT.md              Derniers résultats
├── data/
│   ├── catalog.json            Paramétrage : assureurs, périmètres, produits, grilles de taux
│   └── samples/                Bordereaux fictifs (5 périmètres, février et mars 2026)
├── knowledge/
│   └── regles-metier.md        Règles métier en langage clair, base de connaissance de l'assistant
└── docs/
```

## Démarrage rapide

Prérequis : Python 3.11 ou plus récent.

**Moteur**

```bash
cd engine
pip install -e ".[dev]"
python -m pytest
python -m commission_engine SANTE_INDIV 2026-03            # calcul d'un périmètre sur un mois
python -m commission_engine ANIMAUX 2026-03 --exclusions
```

**API et assistant**

```bash
cp .env.example .env                                       # renseigner LLM_API_KEY (clé Gemini gratuite)
cd api
pip install -e ../engine -e ".[dev]"
python -m pytest
uvicorn commission_api.main:create_app --factory --reload  # http://localhost:8000/docs
```

Une clé Gemini gratuite s'obtient sans carte bancaire sur [Google AI Studio](https://aistudio.google.com).
Sans clé, l'API démarre quand même : le paramétrage, la simulation et les contrats d'exemple restent disponibles,
seul `/api/chat` répond 503.

Exemple d'appel :

```bash
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d "{\"messages\": [{\"role\": \"user\", \"content\": \"Pourquoi le contrat SI-RESILIE donne-t-il une reprise ?\"}]}"
```

**Évaluation**

```bash
python -m evals.run                                        # depuis la racine, modèles de LLM_MODELS
python -m evals.run --model gemini-3.5-flash-lite --cases contrat-resilie,calcul-mental
```

## Choix techniques

- **Paramétrage déclaratif.** Clés de rapprochement, bases d'exposition, seuils, taux négociés et exclusions sont décrits dans `catalog.json`. Ajouter un périmètre ne demande aucune ligne de code.
- **Montants en `Decimal`**, arrondis au centime de façon explicite : pas d'erreurs d'arrondi des flottants.
- **Traçabilité complète.** Chaque ligne calculée porte l'identifiant de sa règle, la formule détaillée et la provenance du taux. Chaque contrat écarté porte un code d'exclusion.
- **Une seule logique pour l'interface et l'assistant.** Les routes HTTP et les outils du modèle passent par les mêmes services et les mêmes modèles de validation.
- **Garde-fous sur les chiffres en trois niveaux** : consigne du prompt, montants obtenus uniquement par les outils, contrôle a posteriori de chaque montant cité.
- **Boucle d'outils bornée**, avec une trace de chaque appel renvoyée au client.
- **Indépendant du fournisseur de modèle.** Un client compatible OpenAI, Gemini par défaut (plan gratuit), et une chaîne de repli qui bascule sur le modèle suivant quand un modèle est saturé ou à court de quota.
- **Tests sans réseau** : le modèle de langage est remplacé par un modèle scripté, ce qui permet de tester la boucle d'outils, la gestion des erreurs et le contrôle des montants.
- **Données d'exemple générées de façon déterministe**, avec des contrats scénarios dont le nom décrit le cas illustré.

## Feuille de route

- [x] **1. Données fictives et moteur de calcul déterministe**
- [x] **2. API du moteur et appel d'outils par le LLM**
- [x] **3. Jeu d'évaluation des réponses de l'assistant et score de fiabilité**
- [ ] 4. Citations des règles dans les réponses, streaming
- [ ] 5. Interface Next.js : chat, panneau « sous le capot », simulateur de contrat
- [ ] 6. CI, conteneurisation, limitation de débit de la démo publique
- [ ] 7. Démo en ligne et vidéo de présentation
