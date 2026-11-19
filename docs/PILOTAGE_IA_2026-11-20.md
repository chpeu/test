# Le pilotage par l'IA locale — ce qu'elle a le droit de faire

Écrit le 20/11/2026, quand le grand modèle est passé d'« il commente le journal »
à « il peut proposer des réglages ». Une page, pour pouvoir répondre dans six
mois à la question : *pourquoi on lui avait permis ça, et jusqu'où ?*

## Les quatre niveaux

Le réglage qui commande s'appelle `pilote_ia_niveau` (dans `config.py`, puis
surchargé par `config_overrides.json`, et réglable d'un clic dans l'onglet
**IA pilote** de l'interface).

| Niveau | Ce qui se passe |
| --- | --- |
| 0 | rien ne tourne |
| 1 | une phrase de synthèse par heure, écrite en base |
| 2 | + elle propose des réglages, **un humain approuve** (réglage par défaut) |
| 3 | + elle applique seule, avec retour automatique si la mesure est pire |

Le niveau 3 n'est pas activé. Il ne le sera que quand les mesures auront montré
qu'une proposition améliorait le gain moyen des prises.

## La cage : six réglages, avec des bornes

Un réglage qui n'est pas dans cette liste est refusé par le programme, sans
discussion, même bien justifié. Le contrôle se fait **côté serveur**, à l'écriture.

| Réglage | Ce que ça change pour toi | Bornes |
| --- | --- | --- |
| `trailing_min_distance` | à quel point le filet suit de près quand le gain est petit | 0,05 % → 0,40 % |
| `trailing_max_distance` | à quel point le filet se relâche quand le gain grossit | 0,05 % → 0,60 % |
| `trailing_pnl_cap` | le gain où le filet se resserre au maximum | 0,20 % → 3,00 % |
| `trailing_trigger_atr_mult` | le moment où le filet s'enclenche | 0,20 ×ATR → 2,00 ×ATR |
| `gb_min_confidence` | la confiance minimum exigée pour prendre un trade | 30 % → 70 % |
| `volume_multiplier` | combien de volume il exige à l'entrée | 0,50 × → 1,50 × |

**Ce qui n'est pas dans la cage, et n'y entrera pas** sans une décision écrite de
Seb : la taille des prises, les plafonds de perte (par prise, par jour), les
frais et les exceptions de paires, le passage du mode essai au mode réel, les
clés d'API. Ces réglages-là décident de la perte maximale possible. Un test
(`test_l_argent_n_est_pas_dans_la_cage`) empêche qu'ils entrent par accident.

## Une seule chose à la fois, mesurée

1. L'IA propose **une** modification par heure, avec son motif.
2. Un humain approuve (niveau 2) — ou le pilote applique (niveau 3).
3. La valeur d'avant est enregistrée en base avant l'écriture.
4. Tant que cette modification n'a pas été mesurée, **aucune autre** n'est
   proposée.
5. Mesure : gain moyen des `pilote_ia_fenetre_prises` (20) prises avant le
   changement, et après. Si c'est plus mauvais de plus de `pilote_ia_gain_minimum`
   (0,05 point), le réglage **revient tout seul** à sa valeur d'avant, avec la
   trace du pourquoi.

## Ce qui est écrit en base (pour pouvoir juger après coup)

| Table | Contenu |
| --- | --- |
| `ia_bilans` | la phrase de synthèse de l'heure + les chiffres + les alertes |
| `ia_avis` | chaque réponse du modèle (question, réponse, modèle, durée) |
| `ia_decisions` | réglage, valeur avant, valeur après, motif, état, mesures |
| `model_predictions` | le verdict du filtre de confiance, prise par prise |

Dernière ligne importante : `model_predictions` existait depuis le début et
contenait **0 ligne**, alors que le filtre disait « je rejette » dans les
journaux depuis des jours. Sans trace, la question « ce filtre fait-il perdre de
l'argent ? » restait sans réponse. Elle est écrite à chaque verdict
(`core/callbacks/scanner_loop.py` → `core/pilotage_ia.ecrire_prediction_filtre`).

Les **alertes** affichées avec un bilan (« 4 pertes l'une après l'autre », « les
prises de la période perdent de l'argent ») sont calculées par le programme à
partir des nombres, pas racontées par le modèle. Le modèle n'a pas le droit
d'inventer un chiffre : il ne reçoit que ceux sortis de la base.

## Ce qui reste à prouver avant de monter en niveau

1. Assez de décisions appliquées **et mesurées** pour comparer avant/après.
2. Que le filtre de confiance, mesuré sur ses propres traces, mérite son seuil.
3. Que l'histoire des petits modèles existe (table `ml_models` encore vide) avant
   de laisser l'IA relancer un entraînement.

## Comment lire l'onglet « IA pilote »

- en haut : le niveau, le modèle en mémoire vidéo, et une phrase d'état ;
- « Bilan de la dernière heure » : ce qu'elle lit dans les chiffres, plus les
  alertes calculées ;
- « Ce que l'IA propose » : approuver ou rejeter ;
- « Décisions récentes » : avant → après, et la mesure ; un bouton **Annuler**
  remet la valeur d'avant ;
- « Ce qu'elle a le droit de toucher » : la cage, avec les bornes.

Le bouton « Faire un bilan maintenant » sert à vérifier sans attendre l'heure.
