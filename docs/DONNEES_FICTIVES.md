# Données fictives

Ce projet est une démonstration. **Aucune donnée réelle n'y figure** :

- le cabinet (Opaline Courtage), les assureurs (Nordale Assurances, Mutuelle Verdance, Calvane Prévoyance) et les produits sont inventés ;
- les taux, les seuils et le paramétrage des périmètres sont choisis pour illustrer les mécanismes, pas pour refléter un marché ;
- les contrats et cotisations sont générés aléatoirement par un script déterministe (`engine/scripts/generate_samples.py`) ;
- le moteur de calcul a été écrit pour ce projet.

Toute ressemblance avec des noms de sociétés ou de produits existants serait fortuite.

## Ce que le projet reproduit

Les **mécanismes** typiques de la rémunération d'un courtier en assurance de personnes :

- précompte de première année, reprise totale ou partielle, commission linéaire ;
- rapprochement des bordereaux mensuels pour ne commissionner que les mouvements ;
- détection des transitions d'état incohérentes ;
- grilles de taux datées, taux négociés, taux transmis par l'assureur ;
- différentes bases d'exposition et règles propres à chaque périmètre.

## Choix de conception

Tout ce qui varie d'un périmètre à l'autre (clé de rapprochement, base d'exposition, seuils, taux spécifiques, exclusions du linéaire) est **déclaré dans `data/catalog.json`** plutôt que codé en dur. Ajouter un périmètre ne demande aucune modification du moteur.
