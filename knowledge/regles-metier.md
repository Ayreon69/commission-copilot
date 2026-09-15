# Règles de calcul des commissions — Opaline Courtage

> Opaline Courtage, ses assureurs (Nordale Assurances, Mutuelle Verdance, Calvane Prévoyance), ses produits,
> ses taux et ses contrats sont **entièrement fictifs**. Ce document décrit les règles appliquées par le moteur
> de calcul (`engine/`) ; chaque règle porte un identifiant repris dans le détail des lignes calculées.

## 1. Vocabulaire

| Terme | Signification |
|---|---|
| **Bordereau** | Fichier mensuel transmis par l'assureur : la liste des contrats (ou des cotisations) du mois. |
| **Périmètre** | Un ensemble de produits d'un assureur, qui partagent les mêmes règles de calcul. |
| **Précompte (P)** | Commission de première année versée d'avance, dès la souscription, calculée sur la prime annuelle. |
| **Reprise (RP)** | Remboursement de tout ou partie d'un précompte quand le contrat n'a pas vécu assez longtemps. |
| **Linéaire (L)** | Commission des années suivantes, versée au fil des cotisations encaissées. |
| **AFN** | Affaire nouvelle : contrat actif. Les états « en cours », « suspendu », « mis en demeure » et « effet futur » sont traités comme AFN. |
| **SEF** | Sans effet : le contrat n'a jamais démarré. |
| **RES** | Résilié : le contrat a démarré puis s'est arrêté. |
| **Exposition** | Part de la période de référence (en général un an) pendant laquelle le contrat a réellement couru. |
| **Prime annuelle HT** | Prime annuelle hors taxes, base du précompte. |

## 2. Déroulé d'un calcul mensuel

Pour un périmètre et un mois M, le moteur compare le bordereau de contrats de M avec celui du mois précédent (M-1) :

1. **Préparation** des deux bordereaux : états harmonisés, produits réaffectés, contrats hors période écartés.
2. **Contrats anciens** retirés : leur précompte est acquis depuis longtemps.
3. **Rapprochement M / M-1** : seules les lignes *nouvelles ou modifiées* peuvent produire un mouvement.
4. **Transitions d'état incohérentes ou sans enjeu** écartées.
5. **Calcul** du précompte, des reprises et des régularisations.
6. **Linéaire**, calculé séparément à partir du bordereau des cotisations du mois.

Chaque ligne écartée est conservée avec un code d'exclusion (voir §12) : on peut toujours expliquer pourquoi un contrat n'a rien produit.

## 3. Préparation des bordereaux

- **État non reconnu** : une ligne dont l'état n'est ni actif, ni sans effet, ni résilié est écartée (`UNKNOWN_STATE`).
- **Produit réaffecté** : certains numéros de contrat désignent un portefeuille particulier. Exemple : en santé animale, les contrats commençant par `MIG` sont des contrats repris d'un autre courtier, rattachés au produit « Verdance Compagnon (portefeuille repris) » et commissionnés à un taux plus bas.
- **Limite d'ancienneté** : un contrat dont la date d'effet précède la limite du périmètre (par exemple 16 mois avant le mois de calcul) est écarté (`SENIORITY`). La même date limite s'applique aux bordereaux de M et de M-1.
- **Effet trop lointain** : sur certains périmètres, un contrat dont l'effet est prévu plus de N mois après le mois de calcul est écarté pour l'instant (`FUTURE_EFFECT`). Il sera traité quand son effet se rapprochera.

## 4. Contrats anciens

Un contrat en portefeuille depuis au moins le seuil du périmètre (1 an, ou 2 ans pour l'assurance emprunteur), mesuré en jours sur une base de 365,25 jours jusqu'à la fin du mois de calcul, ne relève plus du précompte (`OLD_CONTRACT`). Il est retiré des deux mois comparés. Ses cotisations continuent en revanche de produire du linéaire.

## 5. Le rapprochement entre M et M-1

C'est la règle la plus importante. **Un contrat présent en M-1 et en M avec la même clé ne produit rien en M** : sa commission a déjà été traitée le mois où il est apparu (`ALREADY_KNOWN`).

La clé dépend du périmètre :

| Stratégie | Composition de la clé | Périmètres |
|---|---|---|
| Contrat | n° de contrat + état + date de souscription | Santé individuelle, Emprunteur |
| Garantie | souscripteur + bénéficiaire + n° de contrat + état + garantie | Prévoyance des indépendants |
| Contrat et garantie | n° de contrat + état + garantie | Santé animale |
| Personne et garantie | n° de personne + état + garantie | Autonomie senior |

L'état fait partie de la clé : **quand un contrat change d'état, sa clé change**, il redevient « nouveau » et peut produire un mouvement. C'est ainsi qu'un contrat actif en M-1 et résilié en M déclenche une reprise.

Exemple : un contrat souscrit en janvier, actif en février et toujours actif en mars ne produit rien en mars. S'il est résilié en mars, la ligne « résilié » est nouvelle et une reprise est calculée.

## 6. Transitions d'état écartées

Pour chaque contrat, le moteur compare son premier état connu (M-1, ou M s'il vient d'apparaître) et son dernier état connu (M) :

- **Sans effet ↔ résilié** : passage incohérent (un contrat qui n'a jamais démarré ne peut pas être résilié, et inversement). La ligne est écartée pour contrôle (`STATE_ANOMALY`).
- **Résilié → résilié** ou **sans effet → sans effet**, y compris un contrat qui apparaît directement résilié ou sans effet : aucun précompte n'a été versé, il n'y a rien à reprendre (`STABLE_TERMINATION`).

## 7. Précompte et reprises

Le taux utilisé est le **taux de première année** (voir §9).

**R-P1 — Précompte d'une affaire nouvelle.** Contrat actif nouveau : `prime annuelle HT × taux année 1`.
Un contrat dont la date d'effet et la date de fin sont identiques n'a jamais couru et ne produit rien (`ZERO_DURATION`).
*Exemple : prime de 1 200 €, taux de 120 % → précompte de 1 440 €.*

**R-RP1 — Reprise totale d'un contrat sans effet.** Le précompte est intégralement repris : `−(prime annuelle HT × taux année 1)`.
*Exemple : prime de 900 €, taux de 95 % → reprise de 855 €.*

**R-RP2 — Reprise partielle d'un contrat résilié.** Seule la part non couverte est reprise :
`(prime × taux × exposition) − (prime × taux)`, l'exposition étant mesurée de la date d'effet à la date de résiliation.
Si l'exposition atteint 1 (une période complète couverte), il n'y a pas de reprise (`FULL_YEAR_SERVED`).
*Exemple : prime de 1 000 €, taux de 95 %, effet le 01/10/2025, résiliation le 15/03/2026, base 12 mois.
Octobre à mars, 6 mois sont entamés, soit une exposition de 6/12. Le précompte était de 950 € ; 475 € restent
acquis ; la reprise est de 475 €.*

Les montants sont arrondis au centime (arrondi commercial) à chaque étape affichée dans la formule.

## 8. Régularisation d'un changement de prime

**R-REG.** Sur les périmètres qui le prévoient (santé individuelle, santé animale), un contrat présent en M-1 et en M avec la même clé mais **une prime différente** produit un ajustement :
`(nouvelle prime × taux) − (ancienne prime × taux)`. Un ajustement positif est un précompte complémentaire (P), un ajustement négatif une reprise (RP).

La clé étant identique, seul le montant de la prime a changé : ni l'état, ni la date de souscription. Le taux, lui, ne peut pas changer puisqu'il est figé par la date de souscription.

*Exemple : prime passant de 1 000 € à 1 100 €, taux de 95 % → précompte complémentaire de 95 €.*

Sur les autres périmètres, le changement de prime est ignoré.

## 9. Choix du taux

Le taux de première année est déterminé dans cet ordre :

1. **Taux spécifique du périmètre**, s'il cible le produit, la garantie ou le segment du contrat.
   Exemples : renfort dentaire optionnel en santé individuelle à 20 % ; en emprunteur, primo-accédants à 30 % et rachats de crédit à 42 %.
2. **Taux transmis par l'assureur** dans son fichier, pour les périmètres concernés (emprunteur).
3. **Grille du produit** : chaque produit a des grilles datées. On retient celle en vigueur **à la date de souscription** du contrat, si bien que le taux d'un contrat ne change jamais au cours de sa vie.

Un taux s'exprime en pourcentage de la prime : 1,20 signifie 120 %.
Sans taux applicable, la ligne est écartée (`MISSING_RATE`).

## 10. Commission linéaire

**R-L1.** Pour chaque cotisation encaissée dans le mois : `montant de la cotisation HT × taux des années 2 et suivantes`, taux lu dans la grille du produit à la date de souscription.

Une cotisation ne produit pas de linéaire si :

- c'est un mouvement d'annulation ou d'extourne, code commençant par `A` ou `E` (`LINEAR_MOVEMENT`) ;
- son type de cotisation est exclu sur le périmètre, par exemple `P2` en prévoyance et en santé animale (`LINEAR_PREMIUM_TYPE`) ;
- elle concerne encore la **première année** du contrat, c'est-à-dire une exposition inférieure ou égale à 1 au début de la période couverte, puisque cette année est déjà rémunérée par le précompte (`LINEAR_FIRST_YEAR`). L'autonomie senior fait exception : le linéaire y est versé dès la première année ;
- le produit ne donne pas droit au linéaire, par exemple « Nordale Emprunteur Flex » (`LINEAR_PRODUCT`).

## 11. Exposition

| Base | Calcul |
|---|---|
| 12 mois | nombre de mois entamés ÷ 12 (du 15 janvier au 10 mars : 3/12) |
| 24 mois | nombre de mois entamés ÷ 24 |
| 365 jours | nombre de jours, bornes incluses ÷ 365 |
| 365,25 jours | nombre de jours ÷ 365,25 |
| 730 jours | nombre de jours ÷ 730 |
| Anniversaire | nombre de jours ÷ durée réelle jusqu'à la date anniversaire du contrat (un contrat démarré un 29 février fête son anniversaire le 28 février) |

Un contrat qui se termine le jour même de son effet a une exposition nulle.

## 12. Paramétrage des périmètres

| Périmètre | Assureur | Clé | Exposition | Taux année 1 | Régularisation | Limite d'ancienneté | Seuil « contrat ancien » | Particularités |
|---|---|---|---|---|---|---|---|---|
| Santé individuelle | Nordale | Contrat | 12 mois | Grille produit | Oui | 16 mois | 1 an | Renfort dentaire à 20 % |
| Prévoyance des indépendants | Calvane | Garantie | 365 jours | Grille produit | Non | 16 mois | 1 an | Cotisations P2 sans linéaire |
| Santé animale | Verdance | Contrat et garantie | Anniversaire | Grille produit | Oui | 16 mois | 1 an | Contrats `MIG…` : portefeuille repris ; P2 sans linéaire |
| Assurance emprunteur | Nordale | Contrat | 24 mois | Fichier assureur, puis grille | Non | 25 mois | 2 ans | Primo 30 %, rachat 42 % ; Flex sans linéaire |
| Autonomie senior | Calvane | Personne et garantie | 365,25 jours | Grille produit | Non | Aucune | 1 an | Effet à plus de 4 mois écarté ; linéaire dès la 1re année |
| Obsèques | Verdance | — | — | — | — | — | — | Périmètre arrêté : aucun calcul |

## 13. Codes d'exclusion

| Code | Signification |
|---|---|
| `UNKNOWN_STATE` | État du contrat non reconnu |
| `SENIORITY` | Date d'effet antérieure à la limite d'ancienneté |
| `FUTURE_EFFECT` | Date d'effet trop éloignée dans le futur |
| `OLD_CONTRACT` | Contrat ancien : précompte déjà acquis |
| `ALREADY_KNOWN` | Même clé qu'en M-1 : déjà commissionné |
| `STATE_ANOMALY` | Passage incohérent entre sans effet et résilié |
| `STABLE_TERMINATION` | Contrat résilié ou sans effet sans historique actif |
| `ZERO_DURATION` | Effet et fin le même jour |
| `FULL_YEAR_SERVED` | Résiliation après une période complète : pas de reprise |
| `MISSING_RATE` | Aucun taux applicable |
| `LINEAR_MOVEMENT` | Mouvement d'annulation ou d'extourne |
| `LINEAR_PREMIUM_TYPE` | Type de cotisation exclu du linéaire |
| `LINEAR_PRODUCT` | Produit sans commission linéaire |
| `LINEAR_FIRST_YEAR` | Cotisation de première année, couverte par le précompte |
