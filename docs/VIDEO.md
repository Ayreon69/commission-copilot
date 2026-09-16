# Vidéo de présentation — script (≈ 2 min 30)

Objectif : montrer en moins de trois minutes le problème, le principe « le LLM explique, le moteur calcule » et la
preuve de fiabilité. Enregistrement d'écran de la démo en ligne, voix off, 1080p.

| Temps | À l'écran | Voix off |
|---|---|---|
| 0:00 – 0:15 | Page d'accueil, titre | « Dans un cabinet de courtage, personne ne sait vraiment pourquoi un contrat a rapporté tel montant. Les règles sont dans le code. » |
| 0:15 – 0:35 | Schéma de `docs/ARCHITECTURE.md` | « Un modèle de langage peut inventer un taux avec aplomb. Ici, il n'a pas le droit de calculer : il explique, un moteur déterministe chiffre. » |
| 0:35 – 1:10 | Assistant : « Pourquoi le contrat SI-RESILIE donne-t-il une reprise ? ». Le texte arrive en streaming, puis ouvrir « Sous le capot » | « L'assistant appelle le moteur. Sous le capot : l'historique du contrat, la formule, −1 044,50 €, et le tampon : la règle R-RP2 a bien été appliquée par le moteur. » |
| 1:10 – 1:35 | Suggestion « Tester les garde-fous » : demander de calculer de tête | « Si on lui demande un chiffre sans passer par le moteur, il refuse. Chaque montant de la réponse est comparé aux résultats des outils. » |
| 1:35 – 2:00 | Simulateur, cas « Taux négocié » → 336 €, puis « Demander à l'assistant d'expliquer » | « Le simulateur utilise le même moteur. L'évaluation a révélé un bug : un segment mal orthographié appliquait le taux standard, 280 € au lieu de 336. Les segments sont désormais imposés. » |
| 2:00 – 2:20 | `evals/RAPPORT.md`, puis la CI verte sur GitHub | « 27 questions de référence, vérifiées sans modèle juge : 25 réussies, zéro montant sans source. Tests, types et images Docker vérifiés à chaque push. » |
| 2:20 – 2:30 | Page d'accueil, lien du dépôt | « Données entièrement fictives. Le code et la démo sont en lien. » |

**Conseils de tournage.** Réveiller l'API avant d'enregistrer (hébergement gratuit en veille). Zoom navigateur à
110 %. Couper les temps d'attente du modèle au montage plutôt que de relancer.
