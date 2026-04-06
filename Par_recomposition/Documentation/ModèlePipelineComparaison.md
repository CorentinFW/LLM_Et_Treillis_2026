# Modèle de pipeline de comparaison des algorithmes

## Objectif

Ce document propose un pipeline de comparaison en plusieurs étages pour les trois implémentations du projet :

- FCA4J
- `Claude_Opus-4.6/Python/lattice2.py`
- `GPT-5.3-Codex/Python/lattice.py`

L’idée centrale est de ne pas comparer les algorithmes uniquement sur le temps d’exécution, mais dans un ordre de validation plus robuste :

1. **Exactitude** : les treillis produits sont-ils identiques sur le plan logique ?
2. **Performance** : combien de temps consomme chaque approche ?
3. **Scalabilité** : comment le coût évolue-t-il quand la taille du contexte augmente ?
4. **Mémoire / I-O** : quelle est la pression mémoire et disque ?
5. **Robustesse / reproductibilité / tuning** : l’algorithme reste-t-il stable, comparable et réglable ?

Ce pipeline est conçu pour être exploitable avec les fichiers déjà présents dans le projet, en particulier `Documentation/PistesComparaison.md`, `Outils/compare_lattices.py`, `Outils/fast_time.sh`, `Outils/run_with_cpu_time.py` et `Outils/induced_to_full_dot.py`.

---

## Principe directeur

Le pipeline doit fonctionner comme une suite de filtres.

- Une étape valide la précédente.
- Une étape n’a de sens que si les étapes antérieures sont satisfaites.
- Les comparaisons les plus coûteuses ne sont lancées que sur les cas déjà validés.

### Logique de décision

On peut résumer la logique ainsi :

- Si les treillis ne sont pas équivalents, on s’arrête et on corrige la validité.
- Si les treillis sont équivalents, on compare ensuite le coût d’exécution.
- Si les performances sont proches, on affine avec la scalabilité.
- Si deux algorithmes restent proches, la mémoire et l’I/O servent à départager les approches.
- Quand les écarts sont faibles sur tous les critères principaux, on teste la robustesse, la reproductibilité et l’intérêt d’un tuning ciblé.

Ce schéma évite les comparaisons trompeuses, par exemple un algorithme rapide mais incorrect, ou un algorithme très sobre en mémoire mais non reproductible.

---

## Étape 0 - Normalisation préalable

Avant toute comparaison, les sorties doivent être rendues comparables.

### Rôle

Cette étape prépare les fichiers de sortie pour éviter les faux écarts dus au format.

### Actions

- Générer le DOT de chaque algorithme sur le même contexte.
- Si nécessaire, convertir les treillis induits en treillis complets avec `Outils/induced_to_full_dot.py`.
- Comparer les DOT avec `Outils/compare_lattices.py`, qui neutralise la numérotation locale des nœuds.

### Pourquoi c’est indispensable

Les implémentations du projet n’expriment pas toutes les concepts de la même façon.

- FCA4J produit un DOT avec une convention Graphviz spécifique.
- Les scripts Python produisent des labels plus orientés vers la réduction ou l’induction.
- Le comparateur basé sur signatures canoniques permet de comparer la structure logique et pas seulement la forme.

### Sortie attendue

- un verdict d’équivalence ou de différence
- une cartographie des nœuds correspondants
- les divergences de signatures et d’arêtes si elles existent

### Critère de passage

L’étape suivante n’est autorisée que si les treillis sont équivalents sur le plan logique.

---

## Étape 1 - Exactitude

### Position dans le pipeline

C’est la porte d’entrée du modèle. Aucun score de performance n’est interprétable sans cette validation.

### Méthode de comparaison

Comparer les treillis sur trois dimensions :

1. présence des mêmes concepts
2. présence des mêmes relations de couverture
3. cohérence des signatures logiques des nœuds

Le fichier `Outils/compare_lattices.py` fournit déjà cette logique de comparaison.

### Pourquoi cette étape est la première

Cette étape répond à la question la plus importante : les algorithmes calculent-ils le même treillis ?

Si la réponse est non, il est inutile de comparer le temps d’exécution comme si les algorithmes étaient équivalents. Un algorithme faux mais rapide n’est pas un gagnant.

### Mise en oeuvre dans le projet

- Utiliser la famille de datasets déjà présents dans `FCA4J/` et dans les dossiers Python.
- Lancer les calculs sur le même CSV.
- Comparer les DOT complets avec `compare_lattices.py`.
- Archiver le rapport de comparaison dans le dossier du dataset concerné.

### Indicateurs à retenir

- équivalence oui/non
- nombre de signatures communes
- signatures absentes d’un côté
- ambiguïtés de signature
- arêtes normalisées différentes

### Interprétation

- Si l’équivalence est vraie, l’algorithme passe au niveau suivant.
- Si l’équivalence échoue, le pipeline s’arrête : il faut d’abord corriger la logique de calcul ou le format de sortie.

---

## Étape 2 - Performance

### Position dans le pipeline

Cette étape compare les algorithmes corrects entre eux.

### Méthode de comparaison

Mesurer le temps CPU et, si utile, la durée affichée par l’outil de calcul.

Le projet fournit déjà un support clair :

- `Outils/run_with_cpu_time.py` pour les scripts Python
- `Outils/fast_time.sh` pour orchestrer les exécutions et archiver les logs
- le mode `-v` ou les messages de FCA4J pour récupérer les durées internes

### Pourquoi cette étape vient après l’exactitude

Parce qu’un temps d’exécution n’a de valeur que si la sortie est correcte. Sinon, on compare seulement la vitesse de production d’un résultat faux.

### Métriques recommandées

- temps CPU moyen
- médiane du temps CPU
- minimum et maximum
- écart relatif entre runs
- ratio temps / nombre de concepts
- ratio temps / nombre d’arêtes

### Mise en oeuvre dans le projet

Le pipeline peut s’appuyer sur les logs déjà produits dans `TimeRecord/`.

Recommandation pratique :

- exécuter chaque algorithme plusieurs fois sur un même dataset
- conserver toutes les traces brutes
- agréger ensuite les résultats par médiane

### Lecture des résultats

- Un algorithme plus rapide sur les petits datasets peut perdre son avantage sur les grands.
- Un algorithme plus lent en moyenne peut rester intéressant s’il est beaucoup plus stable ou plus sobre en mémoire.

---

## Étape 3 - Scalabilité

### Position dans le pipeline

La scalabilité vient après la performance brute, car elle explique la tendance de fond.

### Méthode de comparaison

Comparer l’évolution des coûts quand on passe d’un contexte petit à un contexte plus grand.

Les jeux `eg9_9`, `eg20_20`, `eg30_30`, `eg40_40`, `eg50_50` et `eg80_80` sont particulièrement adaptés, car ils permettent d’observer une montée en charge progressive.

### Pourquoi cette étape est utile

Un seul benchmark ne suffit pas. Deux algorithmes peuvent être proches sur un petit contexte et diverger fortement quand le nombre de concepts explose.

La scalabilité permet de détecter :

- les approches qui décrochent vite
- les approches qui encaissent mieux la croissance
- les implémentations dont le coût n’augmente pas linéairement avec le contexte

### Indicateurs à retenir

- évolution du temps en fonction de |G| et |M|
- évolution du nombre de concepts
- évolution du nombre d’arêtes
- ratio temps / concept
- ratio temps / arête
- pente empirique entre les tailles de dataset

### Mise en oeuvre dans le projet

- exploiter la série synthétique `eg*_*`
- comparer sur des datasets réels binarisés pour observer la robustesse structurelle
- tracer les courbes à partir des logs archivés dans `TimeRecord/`

### Lecture des résultats

- Un algorithme peut être meilleur à taille fixe mais moins bon en montée en charge.
- La scalabilité aide à distinguer un avantage local d’un avantage structurel.

---

## Étape 4 - Mémoire et I-O

### Position dans le pipeline

Cette étape devient prioritaire dès que les datasets grossissent ou que la mémoire disponible devient contrainte.

### Méthode de comparaison

Comparer :

- le pic mémoire
- le volume de fichiers intermédiaires
- le coût de rechargement et de fusion
- le nombre d’accès disque ou d’étapes de persistance

### Pourquoi cette étape est pertinente dans ce projet

Le code du projet montre trois stratégies différentes :

- FCA4J : exécution JVM avec structures configurables via `-m`
- `Claude_Opus-4.6/Python/lattice2.py` : partitionnement disque puis rechargement global
- `GPT-5.3-Codex/Python/lattice.py` : stockage intermédiaire SQLite puis calcul des arêtes via index

Ces différences justifient une comparaison mémoire/I-O séparée du temps brut.

### Indicateurs à retenir

- mémoire maximale consommée
- taille des partitions ou de la base intermédiaire
- temps de génération des concepts
- temps de fusion/rechargement
- temps de calcul des arêtes

### Mise en oeuvre dans le projet

- utiliser des datasets moyens et grands
- encapsuler les commandes dans une mesure mémoire de type `time -v` si besoin
- exploiter les artefacts déjà générés par les scripts Python
- comparer les fichiers temporaires et la taille des répertoires de travail

### Lecture des résultats

- Un algorithme qui consomme plus de disque peut rester intéressant s’il évite un pic mémoire trop élevé.
- Un algorithme très rapide mais gourmand en RAM peut être moins exploitable sur certaines machines.

---

## Étape 5 - Robustesse

### Position dans le pipeline

La robustesse intervient après les comparaisons de coût, pour vérifier que l’algorithme tient dans des conditions moins favorables.

### Méthode de comparaison

Tester la capacité à terminer correctement dans des scénarios variés :

- fichier vide
- fichier mal formé
- séparateur incorrect
- dataset dense
- timeout limité

### Pourquoi c’est important

Un algorithme de treillis doit être non seulement correct, mais aussi exploitable. Les messages d’erreur, le comportement sous timeout et la capacité à reprendre une exécution partielle comptent réellement dans un projet expérimental.

### Indicateurs à retenir

- réussite ou échec
- qualité du message d’erreur
- présence d’artefacts partiels réutilisables
- respect des limites de temps

### Mise en oeuvre dans le projet

- utiliser les options de FCA4J, notamment `-timeout`
- vérifier les réactions des scripts Python sur des entrées invalides
- consigner les cas d’échec dans les logs de test

### Lecture des résultats

- Une bonne robustesse peut compenser un léger déficit de performance.
- Un algorithme instable doit être relégué, même s’il est rapide sur les cas nominalement simples.

---

## Étape 6 - Reproductibilité

### Position dans le pipeline

La reproductibilité doit être vérifiée après la robustesse, car elle garantit que les résultats observés sont stables d’un run à l’autre.

### Méthode de comparaison

Relancer plusieurs fois les mêmes expériences et vérifier :

- que le treillis obtenu reste équivalent
- que les nombres de concepts et d’arêtes restent identiques
- que les temps restent dans une plage raisonnable

### Pourquoi cette étape est utile

Un bon résultat ponctuel n’est pas suffisant. Dans un projet scientifique, le même protocole doit produire des résultats cohérents.

### Indicateurs à retenir

- variance du temps
- stabilité des artefacts produits
- stabilité des hash ou des DOT après normalisation

### Mise en oeuvre dans le projet

- conserver les runs dans `TimeRecord/`
- archiver les DOT dans les dossiers `Lattice/`
- comparer automatiquement les treillis avec `compare_lattices.py`

### Lecture des résultats

- Un algorithme reproductible facilite la comparaison entre auteurs, machines et exécutions.
- Une sortie variable doit être considérée avec prudence, même si elle est correcte sur le fond.

---

## Étape 7 - Tuning sur les cas critiques

### Position dans le pipeline

Le tuning doit venir en dernier. On ne règle les paramètres qu’après avoir validé la logique, la performance de base, la robustesse et la reproductibilité.

### Méthode de comparaison

Comparer plusieurs réglages sur un sous-ensemble de datasets difficiles ou représentatifs.

Paramètres déjà visibles dans le projet :

- FCA4J : `-m`, `-a`, `-timeout`, `-d`
- `Claude_Opus-4.6/Python/lattice2.py` : taille de batch, taille de chunk, politique de partitionnement
- `GPT-5.3-Codex/Python/lattice.py` : nombre de partitions, taille de chunk, groupement d’ingestion SQLite, intervalle de progression

### Pourquoi cette étape est importante

Le tuning permet de distinguer :

- la qualité intrinsèque de l’algorithme
- l’impact des paramètres de configuration

### Indicateurs à retenir

- gain de temps obtenu par réglage
- surcoût mémoire éventuel
- stabilité des résultats après réglage
- sensibilité aux paramètres

### Mise en oeuvre dans le projet

- choisir une grille de paramètres courte mais pertinente
- conserver les paramètres exacts dans les logs
- ne tuner que sur les cas qui restent critiques après les autres étapes

### Lecture des résultats

- Si un algorithme devient très bon seulement après tuning, il faut le signaler clairement.
- Si un algorithme est déjà bon avec ses réglages par défaut, c’est un point fort pratique important.

---

## Ordonnancement recommandé du pipeline

Le pipeline conseillé pour ce projet est le suivant :

1. **Normalisation** : générer les sorties comparables.
2. **Exactitude** : vérifier l’équivalence structurelle.
3. **Performance** : mesurer le temps CPU.
4. **Scalabilité** : observer la montée en charge.
5. **Mémoire / I-O** : analyser la consommation des ressources.
6. **Robustesse** : tester les situations limites.
7. **Reproductibilité** : relancer et vérifier la stabilité.
8. **Tuning** : ajuster seulement sur les cas critiques.

Ce séquencement est volontairement conservateur. Il privilégie la validité scientifique avant l’optimisation.

---

## Modèle d’exploitation dans le projet

### Structure de dossiers conseillée

- `TimeRecord/<dataset>/` pour les journaux d’exécution
- `FCA4J/<dataset>/Lattice/` pour les sorties de référence
- `Claude_Opus-4.6/Python/<dataset>/Lattice/` et `GPT-5.3-Codex/Python/<dataset>/Lattice/` pour les sorties des scripts Python

### Artefacts à conserver

- les DOT générés
- les rapports de comparaison
- les logs bruts de timing
- les fichiers intermédiaires utiles au diagnostic

### Ce qui doit être considéré comme une preuve de comparaison

Pour qu’une comparaison soit recevable, il faut au minimum :

- un dataset commun
- des sorties générées par les trois implémentations
- un rapport d’équivalence structurelle
- des mesures de coût associées au même protocole

---

## Conclusion

Le meilleur modèle de comparaison pour ce projet n’est pas un score unique, mais une chaîne de validation.

- **Exactitude** donne la légitimité.
- **Performance** donne l’intérêt pratique.
- **Scalabilité** donne la projection sur les grands cas.
- **Mémoire / I-O** révèle les compromis réels d’implémentation.
- **Robustesse**, **reproductibilité** et **tuning** terminent l’évaluation en montrant si l’approche est exploitable dans un cadre expérimental sérieux.

En pratique, ce pipeline permet de désigner les points forts de chaque algorithme sans réduire la comparaison à une simple course au temps.