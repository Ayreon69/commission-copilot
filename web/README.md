# Interface — Commission Copilot

Interface Next.js de l'assistant et du simulateur. Elle ne contient aucune logique de calcul : tout passe par l'API
FastAPI (`../api`).

## Lancer

```bash
cp .env.example .env.local        # adresse de l'API, http://localhost:8000 par défaut
npm install
npm run dev                       # http://localhost:3000
```

L'API doit tourner en parallèle : `uvicorn commission_api.main:create_app --factory` depuis n'importe quel dossier.

## Vues

- **Assistant** : conversation en streaming (Server-Sent Events). Le panneau « Sous le capot » montre, pour la
  réponse sélectionnée, les appels au moteur et leurs paramètres, les lignes calculées avec leurs formules, les règles
  citées (tampon « appliquée par le moteur ») et les contrôles : montants sans source, règles ou produits inexistants.
- **Simulateur** : formulaire relié directement au moteur, sans modèle de langage, avec des cas types, une frise du
  contrat (période couverte, mois de calcul) et un bordereau de résultat. Un bouton prépare une question pour
  l'assistant à partir du cas simulé.

## Types de l'API

Les types TypeScript sont générés depuis le schéma OpenAPI de l'API, pour que l'interface et l'API ne divergent pas :

```bash
cd ../api && python scripts/export_openapi.py     # écrit web/openapi.json
cd ../web && npm run types                        # régénère src/lib/api-types.ts
```

## Vérifications

```bash
npm run typecheck && npm run lint && npm run build
```
