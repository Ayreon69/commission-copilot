# Bordereaux d'exemple

Données **100 % fictives**, générées par `engine/scripts/generate_samples.py` (génération déterministe).
Ne pas modifier ces fichiers à la main : relancer le script. Un test vérifie qu'ils sont à jour.

Chaque périmètre contient trois fichiers pour le calcul de mars 2026 :

| Fichier | Contenu |
|---|---|
| `contracts_2026-02.csv` | Bordereau de contrats du mois précédent (M-1) |
| `contracts_2026-03.csv` | Bordereau de contrats du mois de calcul (M) |
| `premiums_2026-03.csv` | Cotisations encaissées en mars, base du linéaire |

## Contrats scénarios

Le numéro de ces contrats décrit le cas qu'ils illustrent (préfixe du périmètre : `SI`, `PT`, `AN`, `EM`, `DE`).
Les autres contrats (`SI-0001`…) forment un portefeuille aléatoire réaliste.

| Scénario | Situation | Résultat attendu |
|---|---|---|
| `NOUVEAU` | Contrat actif apparu en mars | Précompte (R-P1) |
| `STABLE` | Actif en février et en mars | Rien : déjà commissionné |
| `SANS-EFFET` | Actif en février, sans effet en mars | Reprise totale (R-RP1) |
| `RESILIE` | Actif en février, résilié le 15 mars | Reprise partielle (R-RP2) |
| `RESILIE-SANS-HISTORIQUE` | Apparaît directement résilié | Rien : aucun précompte versé |
| `ANOMALIE` | Sans effet en février, résilié en mars | Écarté pour contrôle |
| `ANCIEN` | En portefeuille depuis plus que le seuil | Rien en précompte, linéaire sur ses cotisations |
| `TROP-ANCIEN` | Effet avant la limite d'ancienneté | Écarté |
| `EFFET-DIFFERE` | Effet trop lointain (autonomie senior) | Écarté |
| `HAUSSE-PRIME` / `BAISSE-PRIME` | Prime modifiée entre février et mars | Régularisation (R-REG) si le périmètre la prévoit |
| `DUREE-NULLE` | Effet et fin le même jour | Rien |
| `PRODUIT-INCONNU` | Produit absent du catalogue | Écarté : aucun taux |
| `TAUX-SPECIFIQUE-n` | Garantie ou segment à taux négocié | Précompte au taux spécifique |
| `MIG-AN-NOUVEAU` | Contrat du portefeuille repris (santé animale) | Précompte au taux du produit repris |
| `PORTEFEUILLE-nnn` | Cotisation d'un contrat de plusieurs années | Linéaire (R-L1) |
| `ANNULATION` / `EXTOURNE` | Mouvements négatifs | Écartés du linéaire |
