# Description

`compare_lattices.py` est un script Python en ligne de commande qui compare deux fichiers Graphviz `.dot` représentant des treillis de concepts.

Son objectif est de déterminer si deux treillis sont **logiquement équivalents**, même lorsque les identifiants locaux des nœuds diffèrent d’un fichier à l’autre. La comparaison ne repose donc pas sur la numérotation des nœuds, mais sur une **signature canonique** reconstruite à partir du contenu des concepts.

Concrètement, le script :

- lit deux fichiers `.dot` ;
- extrait les nœuds et les arêtes ;
- reconstruit, pour chaque nœud, une signature logique à partir de son label Graphviz ;
- compare les signatures entre les deux fichiers ;
- détecte les signatures absentes d’un côté, présentes uniquement dans un fichier, ou ambiguës ;
- compare ensuite les arêtes après normalisation, lorsque la correspondance entre nœuds est complète ;
- produit un verdict final d’équivalence ou de différence.

Cet outil est utile pour vérifier qu’un treillis généré, transformé ou recomposé reste identique sur le plan logique, même si la représentation DOT change localement.

## Fonctionnalités principales

- Comparaison de deux treillis Graphviz `.dot`.
- Indépendance vis-à-vis des identifiants locaux des nœuds.
- Reconstruction d’une signature canonique de concept à partir de :
  - la partie `(I, E)` ;
  - la liste des attributs ;
  - la liste des objets.
- Détection des signatures présentes uniquement dans un des deux fichiers.
- Détection des signatures ambiguës dans un fichier donné.
- Comparaison des arêtes après renumérotation logique des nœuds.
- Sortie humaine lisible par défaut.
- Sortie JSON complète via l’option `--json`.
- Verdict minimal via l’option `--simple`.
- Code de retour exploitable dans des scripts d’automatisation.

## Technologies utilisées

- Python
- Bibliothèques standard Python : `argparse`, `json`, `re`, `collections`, `dataclasses`, `pathlib`, `typing`
- Format Graphviz DOT

## Prérequis

- Une installation Python 3 disponible en ligne de commande.
- Deux fichiers Graphviz `.dot` représentant des treillis de concepts.

Aucune dépendance externe n’est visible dans le script : son exécution semble reposer uniquement sur la bibliothèque standard de Python.

## Installation

Aucune installation spécifique ne semble nécessaire en dehors de Python.

Depuis le répertoire contenant le script, ou en lui passant son chemin, il peut être exécuté directement avec l’interpréteur Python.

Exemple :

```bash
python Outils/compare_lattices.py file1.dot file2.dot
```

## Utilisation

### Syntaxe

```bash
python Outils/compare_lattices.py <file1> <file2> [--json | --simple]
```

### Arguments positionnels

- `file1` : chemin du premier fichier `.dot`
- `file2` : chemin du second fichier `.dot`

### Options

- `--json` : affiche le rapport complet au format JSON
- `--simple` : affiche uniquement le verdict d’équivalence

Les options `--json` et `--simple` sont mutuellement exclusives.

## Format des fichiers attendus

Le script compare des fichiers Graphviz DOT contenant :

- des **nœuds** avec un label décrivant un concept ;
- des **arêtes** orientées entre ces nœuds.

Le label attendu pour un nœud suit une structure de type :

```text
{id (I: x, E: y)|attributs|objets}
```

Exemple de forme logique attendue :

```text
{12 (I: 2, E: 3)|a|o1|o2|o3}
```

ou, selon le format exact du DOT, une représentation équivalente avec séparateurs, retours à la ligne ou échappements Graphviz.

Le point important est que le script s’appuie sur trois éléments :

- `(I: x, E: y)`
- les attributs
- les objets

L’identifiant local placé au début du label est ignoré pour la comparaison logique.

## Structure de la comparaison

La comparaison se déroule en plusieurs étapes.

### 1. Lecture du graphe DOT

Le script lit chaque fichier et extrait :

- les nœuds ;
- leurs labels ;
- les arêtes orientées.

### 2. Construction d’une signature canonique

Pour chaque nœud, le script reconstruit une signature logique indépendante de son identifiant DOT local.

Cette signature est construite à partir de :

- la partie `(I, E)` ;
- l’ensemble des attributs ;
- l’ensemble des objets.

Les attributs et objets sont normalisés pour limiter l’impact des variations de présentation, par exemple :

- ordre d’énumération ;
- espaces ;
- sauts de ligne ;
- encodages Graphviz comme `\n`.

En pratique, deux nœuds sont considérés comme correspondants s’ils portent la même signature canonique.

### 3. Correspondance entre nœuds

Le script compare les signatures présentes dans chaque fichier afin de :

- construire la correspondance entre nœuds ;
- repérer les signatures présentes uniquement dans `file1` ;
- repérer les signatures présentes uniquement dans `file2` ;
- signaler les signatures ambiguës, c’est-à-dire associées à plusieurs nœuds dans un même fichier.

### 4. Comparaison des arêtes normalisées

Si la correspondance des nœuds est complète et non ambiguë, le script renomme logiquement les nœuds communs avec des identifiants partagés, puis compare les arêtes sur cette base normalisée.

Cette étape permet de vérifier non seulement que les concepts correspondent, mais aussi que la structure du treillis est la même.

## Sorties et codes de retour

### Sortie par défaut

Sans option, le script produit un rapport texte lisible comprenant notamment :

- le verdict final ;
- la correspondance entre nœuds ;
- les signatures présentes uniquement dans un fichier ;
- les signatures ambiguës ;
- le bilan sur les arêtes normalisées.

### Sortie JSON

Avec `--json`, le script affiche un rapport structuré contenant notamment :

- `equivalent` ;
- `ambiguous` ;
- les hypothèses de comparaison ;
- les nombres de nœuds et d’arêtes ;
- les correspondances ;
- les signatures présentes d’un seul côté ;
- les signatures ambiguës ;
- les arêtes normalisées ;
- les différences d’arêtes.

Cette sortie est adaptée à un traitement automatisé.

### Sortie simple

Avec `--simple`, le script affiche uniquement un verdict court :

- `Les deux treillis sont équivalents.`
- ou `Les deux treillis sont différents.`

### Codes de retour

- `0` : les deux treillis sont équivalents
- `1` : les deux treillis sont différents

Ces codes sont particulièrement utiles dans :

- des scripts shell ;
- des tests automatisés ;
- des pipelines de validation.

## Exemples d’utilisation

### Comparaison standard

```bash
python Outils/compare_lattices.py \
  FCA4J/Animals11/Lattice/Animals11.dot \
  GPT-5.1/Animals11/Lattice/Animals11.dot
```

Cette commande affiche un rapport humain lisible indiquant si les deux treillis sont logiquement équivalents.

### Rapport JSON complet

```bash
python Outils/compare_lattices.py \
  FCA4J/eg9_9/Lattice/eg9_9.dot \
  GPT-5.1/eg9_9/Lattice/eg9_9.dot \
  --json
```

Utile pour intégrer le résultat dans un autre programme ou pour archiver un rapport structuré.

### Verdict minimal pour un script

```bash
python Outils/compare_lattices.py \
  FCA4J/eg20_20/Lattice/eg20_20.dot \
  GPT-5.1/eg20_20/Lattice/eg20_20.dot \
  --simple
```

Cette forme est adaptée si seul le verdict final vous intéresse.

### Exploitation du code de retour en shell

```bash
python Outils/compare_lattices.py file1.dot file2.dot --simple
status=$?

if [ "$status" -eq 0 ]; then
  echo "Treillis équivalents"
else
  echo "Treillis différents"
fi
```

## Hypothèses et limites

Le script repose sur les hypothèses explicites suivantes :

- chaque nœud logique possède une signature canonique unique dans un fichier donné ;
- les labels de concepts suivent une structure de type `{id (I: x, E: y)|attributs|objets}` ;
- les différences de formatage n’altèrent pas le contenu logique.

Points d’attention :

- si plusieurs nœuds partagent la même signature dans un même fichier, la comparaison devient ambiguë ;
- si le label ne respecte pas suffisamment la structure attendue, l’analyse peut échouer ;
- la comparaison structurelle des arêtes n’est effectuée que si les nœuds ont pu être appariés complètement et sans ambiguïté ;
- l’outil est centré sur des treillis de concepts décrits dans le format attendu, et non sur des graphes DOT arbitraires.

## Quand utiliser ce script ?

`compare_lattices.py` est pertinent lorsque vous souhaitez :

- vérifier qu’un treillis produit par deux générateurs différents est le même sur le plan logique ;
- comparer un treillis initial et un treillis recomposé ;
- valider qu’une transformation de fichier DOT n’a pas modifié le contenu conceptuel ;
- automatiser une vérification d’équivalence dans un flux de traitement.

En résumé, ce script répond à une question simple : **les deux fichiers DOT décrivent-ils le même treillis de concepts, indépendamment des identifiants locaux des nœuds ?**
