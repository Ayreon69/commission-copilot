# Déploiement de la démo

Deux hébergements gratuits, sans carte bancaire :

| Partie | Hébergeur | Pourquoi |
|---|---|---|
| API (FastAPI, image Docker) | Render, offre gratuite | Déploiement du `Dockerfile` existant, HTTPS, santé sur `/api/health` |
| Interface (Next.js) | Vercel, offre Hobby | Hébergeur de référence pour Next.js, déploiement à chaque push |

**Contrepartie assumée** : l'API Render se met en veille après 15 minutes sans trafic. Le premier visiteur attend
jusqu'à une minute ; l'interface l'indique (« Réveil de l'API ») et réessaie jusqu'à ce que l'API réponde.

## 1. API sur Render

1. Sur [render.com](https://render.com), **New → Blueprint**, puis choisir le dépôt GitHub. Render lit `render.yaml`.
2. Renseigner les deux variables secrètes demandées :
   - `LLM_API_KEY` : clé Gemini (Google AI Studio) ;
   - `CORS_ORIGINS` : adresse de l'interface, connue après l'étape 2 (on peut la compléter ensuite).
3. Vérifier `https://<service>.onrender.com/api/health`.

## 2. Interface sur Vercel

1. Sur [vercel.com](https://vercel.com), **Add New → Project**, importer le dépôt.
2. **Root Directory** : `web`.
3. Variable d'environnement `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com` (sans barre finale).
4. Déployer, puis reporter l'adresse Vercel dans `CORS_ORIGINS` sur Render.

## 3. Contrôle

- Le badge en haut à droite affiche le nom du modèle.
- Simulateur, cas « Résiliation » : −98,50 €.
- Assistant : « Pourquoi le contrat SI-RESILIE donne-t-il une reprise ? » → −1 044,50 €, règle R-RP2 appliquée.

## Protéger le quota

Les limites de débit sont réglées dans `render.yaml` (voir [ARCHITECTURE.md](ARCHITECTURE.md#démo-publique--limitation-de-débit)).
Le quota Gemini gratuit est partagé par tous les visiteurs : une clé dédiée à la démo, distincte de celle du
développement, évite qu'une session d'évaluation épuise le quota de la démo publique.
