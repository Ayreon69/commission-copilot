# Commission Copilot

Assistant pour comprendre la rémunération d'un cabinet de courtage en assurance : **un moteur de calcul
déterministe** qui chiffre les commissions et **un assistant conversationnel** qui explique les règles, sans jamais
inventer un montant.

> Toutes les données sont fictives : cabinet, assureurs, produits, taux et contrats. Voir [docs/DONNEES_FICTIVES.md](docs/DONNEES_FICTIVES.md).

## Le problème

Dans un cabinet de courtage, la commission d'un contrat dépend de dizaines de règles : précompte versé d'avance,
reprise si le contrat s'arrête trop tôt, commission linéaire les années suivantes, grilles de taux datées, exceptions
par assureur… Les équipes finance, gestion et commerciales ne peuvent pas lire le code qui applique ces règles :
elles dépendent des développeurs pour savoir *pourquoi* un contrat a rapporté tel montant, ou rien du tout.

## Le principe : le LLM explique, le moteur calcule

Un modèle de langage peut halluciner un taux avec la même assurance qu'il cite une règle exacte. Sur un montant de
commission, l'erreur est coûteuse et invisible. Ce projet sépare donc strictement les rôles :

| Composant | Rôle | Garantie |
|---|---|---|
| **Moteur** (`engine/`) | Calcule chaque commission et justifie chaque exclusion | Déterministe, testé, chaque ligne porte sa règle et sa formule |
| **Assistant** *(à venir)* | Explique les règles, appelle le moteur pour tout chiffrage | Ne produit jamais un montant lui-même |

Exemple de ligne produite par le moteur :

```text
RP  SI-RESILIE   −1 044,50 €  [R-RP2] (2 089,00 € × 120 % × 7/12) − (2 089,00 € × 120 %) = 1 462,30 € − 2 506,80 € = −1 044,50 €
```

## Structure

```text
commission-copilot/
├── engine/                     Moteur de calcul Python (sans dépendance externe)
│   ├── commission_engine/      Préparation, rapprochement M/M-1, précompte, linéaire
│   ├── scripts/                Génération des bordereaux d'exemple
│   └── tests/                  Tests unitaires et scénarios de bout en bout
├── data/
│   ├── catalog.json            Paramétrage : assureurs, périmètres, produits, grilles de taux
│   └── samples/                Bordereaux fictifs (5 périmètres, février et mars 2026)
├── knowledge/
│   └── regles-metier.md        Règles métier en langage clair, base de connaissance de l'assistant
└── docs/
```

## Démarrage rapide

Prérequis : Python 3.11 ou plus récent.

```bash
cd engine
pip install -e ".[dev]"

python -m pytest                              # tests
python -m commission_engine SANTE_INDIV 2026-03 # calcul d'un périmètre sur un mois
python -m commission_engine ANIMAUX 2026-03 --exclusions
python scripts/generate_samples.py            # régénère les bordereaux d'exemple
```

Périmètres disponibles : `SANTE_INDIV`, `PREVOYANCE_TNS`, `ANIMAUX`, `EMPRUNTEUR`, `DEPENDANCE`.

## Choix techniques

- **Paramétrage déclaratif.** Clés de rapprochement, bases d'exposition, seuils, taux négociés et exclusions sont décrits dans `catalog.json`. Un nouveau périmètre ne demande aucune ligne de code.
- **Montants en `Decimal`**, arrondis au centime de façon explicite : pas d'erreurs d'arrondi des flottants.
- **Traçabilité complète.** Chaque ligne calculée porte l'identifiant de sa règle, la formule détaillée et la provenance du taux. Chaque contrat écarté porte un code d'exclusion : on peut toujours répondre à « pourquoi ce contrat n'a rien produit ? ».
- **Clés de rapprochement en tuples**, et non en chaînes concaténées, pour éviter les collisions (`"AB" + "C" == "A" + "BC"`).
- **Données d'exemple générées de façon déterministe**, avec des contrats scénarios nommés d'après le cas qu'ils illustrent. Un test vérifie que chaque scénario produit le résultat attendu sur chaque périmètre.
- **Aucune dépendance** pour le moteur : il pourra être exposé tel quel derrière une API et appelé comme outil par l'assistant.

## Feuille de route

- [x] **1. Données fictives et moteur de calcul déterministe**
- [ ] 2. API du moteur et appel d'outil par le LLM
- [ ] 3. Jeu d'évaluation des réponses de l'assistant et score de fiabilité
- [ ] 4. Citations des règles dans les réponses, streaming
- [ ] 5. Interface Next.js : chat, panneau « sous le capot », simulateur de contrat
- [ ] 6. CI, conteneurisation, limitation de débit de la démo publique
- [ ] 7. Démo en ligne et vidéo de présentation
