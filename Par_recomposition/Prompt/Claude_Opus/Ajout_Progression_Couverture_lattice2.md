# Rôle
Tu es un expert en Python (performance/robustesse), et tu sais instrumenter proprement un algorithme sans en altérer les résultats.

# Contexte
Dans ce dépôt, le script Python [Claude_Opus-4.6/Python/lattice2.py](Claude_Opus-4.6/Python/lattice2.py) calcule un treillis de concepts formels (FCA) à partir d’un CSV binaire, puis calcule la **relation de couverture** (diagramme de Hasse) via la fonction compute_edges(concepts) appelée dans main().

Le script affiche déjà une progression pendant l’énumération des concepts, mais **aucune progression n’est affichée pendant le calcul de la relation de couverture**.

# Objectif
Ajouter un **indice de progression** pendant le **calcul de la relation de couverture** (étape « Calcul de la relation de couverture ... »), affichant :
1) **Temps écoulé depuis le lancement de l’algorithme**
2) **Approximation de l’état du calcul** en pourcentage **entre 0% et 100%**

La progression doit être **mise à jour toutes les 10 minutes** (600 secondes), et doit aussi afficher une ligne finale à **100%** lorsque le calcul se termine.

# Contraintes impératives
- Ne modifie pas le code existant : **ne change aucun octet** de [Claude_Opus-4.6/Python/lattice2.py](Claude_Opus-4.6/Python/lattice2.py).
- Implémente la fonctionnalité **uniquement en ajoutant** un ou plusieurs nouveaux fichiers.
- N’ajoute **aucune dépendance externe** (stdlib Python uniquement).
- Ne change pas les résultats : le fichier DOT généré doit rester **identique** (hors éventuelles lignes de log sur stdout).
- Le surcoût de l’instrumentation doit rester faible (pas de logs à chaque itération, pas d’allocations inutiles).

# Hypothèses autorisées
- Le calcul exact du “pourcentage” n’est pas requis : une **approximation raisonnable** est suffisante.
- Le mécanisme doit fonctionner pour des CSV de tailles variables.

# Stratégie imposée (sans modifier lattice2.py)
Implémente la progression en créant un **wrapper exécutable** qui :
1) importe lattice2.py comme module Python (dans le même dossier)
2) remplace (monkey-patch) lattice2.compute_edges par une version instrumentée
3) appelle lattice2.main() pour exécuter le flux normal

Cela garantit :
- aucun changement dans lattice2.py
- sortie DOT inchangée
- ajout de logs uniquement pendant le calcul des arêtes

# Spécification de la progression
## 1) Mesure du temps
- Mesure le temps écoulé depuis le lancement du wrapper avec time.monotonic().
- Formate le temps sous la forme HH:MM:SS (heures pouvant dépasser 24).

## 2) Approximation du pourcentage
- Calcule un “travail total” approximatif à partir des structures de compute_edges :
  - n = len(concepts)
  - intent_cards[i] = popcount(intent)
  - level_index[level] = indices des concepts de cardinalité = level
- Définis un compteur de travail basé sur le **nombre de candidats parcourus** dans les boucles (approximativement le nombre de tests de sous-ensemble effectués).
- Exemple robuste (recommandé) :
  - pré-calcule level_sizes[level] = len(level_index[level])
  - pré-calcule un préfixe prefix[level] = sum(level_sizes[0..level])
  - estime le total : total_work = sum(prefix[c_card-1] pour chaque concept avec c_card>0)
  - incrémente done_work au fur et à mesure du parcours des niveaux (par exemple done_work += level_sizes[level] après avoir itéré ce niveau)
- Convertis en pourcentage : pct = clamp(100.0 * done_work / max(total_work, 1), 0.0, 100.0).

## 3) Fréquence des logs
- Affiche une ligne **au plus** toutes les 10 minutes.
- Ne fais pas de print plus fréquent (même si le calcul est très long).
- Toujours flush=True.

## 4) Format de log (imposé)
À chaque mise à jour, écris EXACTEMENT une ligne au format :

~~~
[COVER_PROGRESS] elapsed=<HH:MM:SS> approx=<PCT>%
~~~

- <PCT> doit être un nombre avec au moins 1 décimale (ex: 42.3%).
- À la fin du calcul, écris une ligne finale :

~~~
[COVER_PROGRESS] elapsed=<HH:MM:SS> approx=100.0%
~~~

# Étapes à suivre
1) Crée un nouveau fichier exécutable dans le dossier Claude_Opus-4.6/Python/ (choisis un nom explicite, par ex. lattice2_cover_progress.py).
2) Dans ce fichier :
  - importe time et les modules nécessaires
  - ajoute le dossier courant au sys.path si nécessaire
  - import lattice2
  - capture start_time = time.monotonic() avant de lancer le calcul
  - définis compute_edges_with_progress(concepts) :
    - reprends la logique de lattice2.compute_edges à l’identique (mêmes structures, mêmes conditions)
    - ajoute uniquement la logique de progression décrite ci-dessus
    - retourne la même liste edges
  - fais lattice2.compute_edges = compute_edges_with_progress
  - appelle lattice2.main()
3) Vérifie que l’exécution suivante fonctionne :
  - python Claude_Opus-4.6/Python/lattice2_cover_progress.py <chemin/vers/context.csv>
  - le DOT généré a le même nom que celui produit par lattice2.py (car main() est inchangée)
  - des logs [COVER_PROGRESS] ... apparaissent pendant l’étape de couverture si elle dure assez longtemps, puis une ligne finale à 100%.

# Format de sortie attendu de TA réponse
- Ne fournis pas de texte inutile.
- Donne d’abord un résumé très court (2–4 lignes) de ce que tu ajoutes.
- Puis fournis le contenu complet de chaque nouveau fichier, avec son chemin, dans des blocs de code.
- Confirme explicitement que [Claude_Opus-4.6/Python/lattice2.py](Claude_Opus-4.6/Python/lattice2.py) n’a pas été modifié.

# Rappel
- Réfléchis avant d’écrire.
- N’explique pas ton raisonnement détaillé : fournis seulement le résultat final demandé (résumé + fichiers).