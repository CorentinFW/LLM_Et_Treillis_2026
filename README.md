# Capacité des modèles de langage à générer des treillis de concepts

Ce dépôt rassemble un projet de TER de Master 1 en Génie Logiciel consacré à la génération d’algorithmes de treillis de concepts formels par des modèles de langage (LLM, *Large Language Models*).

La question étudiée est : **« Un LLM peut-il calculer un treillis de concepts et des règles d’implication ? »**

Le travail documenté dans ce dépôt porte principalement sur le calcul et la validation structurelle des treillis. Les règles d’implication sont évoquées dans le contexte théorique, mais elles ne font pas l’objet d’une évaluation expérimentale documentée dans les résultats disponibles.

Deux démarches sont comparées :

- une génération directe, centrée sur la production d’un treillis correct ;
- une génération sous contrainte mémoire, qui demande aux modèles de limiter les structures conservées en mémoire et peut recourir à des fichiers intermédiaires ou à une recomposition.

Les sorties générées sont comparées à FCA4J, utilisé comme implémentation de référence, après normalisation de leur représentation Graphviz DOT.

## Question de recherche et objectifs

L’étude cherche à mesurer :

- la capacité à énumérer les concepts formels d’un contexte binaire ;
- la correction des relations de couverture du treillis ;
- l’équivalence structurelle avec la référence FCA4J ;
- le temps d’exécution et la consommation mémoire ;
- l’utilisation éventuelle du disque et la robustesse sur des contextes de tailles et de structures variées.

Une sortie syntaxiquement valide ou un programme qui se termine sans erreur ne suffit donc pas : le treillis doit aussi contenir les bons concepts et les bonnes relations.

## Rappel de l’analyse formelle de concepts

L’analyse formelle de concepts (AFC, ou FCA en anglais) étudie les relations entre un ensemble d’objets et un ensemble d’attributs. Un **contexte formel** associe à chaque couple objet-attribut une valeur binaire indiquant si l’objet possède l’attribut.

Un **concept formel** est formé de deux ensembles liés :

- l’**extension** (*extent*), constituée des objets concernés ;
- l’**intension** (*intent*), constituée des attributs communs à ces objets.

Les concepts sont ordonnés par inclusion de l’extension, ou de manière duale par inclusion de l’intension. Cet ordre forme le **treillis de concepts**. Son **diagramme de Hasse** ne conserve que les relations de couverture : une arête relie deux concepts lorsqu’aucun concept intermédiaire ne se trouve entre eux.

Le rapport scientifique [Rapport.pdf](Rapport.pdf) présente les définitions et les fondements théoriques plus en détail.

## Approches étudiées

### Génération directe : `Par_Algo_Direct/`

Cette branche correspond au travail de **Corentin Fay**. Les modèles reçoivent des prompts demandant un programme capable de lire les contextes, de produire un treillis au format DOT et de rester correct sur des jeux de données de tailles croissantes.

Les modèles référencés dans le benchmark direct sont :

- ChatGPT 5.3 Codex ;
- Claude Sonnet 4.6 ;
- Gemini 3.1 ;
- Qwen ;
- FCA4J comme référence.

Les algorithmes sont exécutés sur les CSV, puis leurs fichiers DOT sont comparés à ceux de FCA4J. Le script `Par_Algo_Direct/outils/run_benchmark.sh` mesure le temps, le pic de mémoire et la taille de sortie pour un exécutable compilé. Les outils `compare_lattices.py` et `induced_to_full_dot.py` servent à la comparaison et à la conversion de sorties lorsque nécessaire.

Les résultats montrent un comportement dépendant à la fois du modèle et du dataset : Claude est équivalent à FCA4J sur plusieurs cas, alors que ChatGPT 5.3 Codex et Qwen échouent sur une partie des jeux réels ou des cas plus grands.

### Génération sous contrainte mémoire : `Par_recomposition/`

Cette branche correspond au travail de **Anthony Hommais**. Les prompts demandent aux LLM de réduire la pression mémoire, notamment en limitant les structures conservées en mémoire, en partitionnant les données, en externalisant des résultats sur disque ou en recomposant ensuite un treillis complet.

Ces mécanismes ne sont pas identiques pour tous les modèles : la présence d’une contrainte dans un prompt ne constitue pas une preuve d’implémentation effective. Le dépôt contient notamment des implémentations Python pour Claude Opus 4.6, GPT-5.1, GPT-5.3 Codex, GPT-5.4, Gemini 2.5 Pro, Gemini 3.1, Kimi K2 et Qwen 3.6, ainsi que des sorties et des essais FCA4J.

Le pipeline modulaire de `Par_recomposition/Outils/` exécute les étapes suivantes :

1. exécution des algorithmes sur un même contexte ;
2. normalisation des DOT induits vers des DOT complets lorsque le format le permet ;
3. comparaison structurelle des sorties normalisées ;
4. génération d’un rapport et de métadonnées par lancement.

La configuration par défaut active seulement `fca4j`, `claude_lattice2` et `gpt53_lattice` sur `eg9_9`, `eg20_20` et `eg30_30`. Les résultats archivés dans `Résultats/Benchmark_avec_restriction_de_mémoire.md` proviennent d’une campagne plus large, avec sept algorithmes et dix-sept datasets ; ils ne doivent pas être confondus avec la configuration par défaut.

## Organisation du dépôt

```text
.
├── Dataset/                         # Jeux de données communs
├── Par_Algo_Direct/                 # Génération directe (Corentin Fay)
│   ├── Large Language Model/        # Sorties et jeux de données par modèle
│   ├── FCA4J/                       # Référence et exécution FCA4J
│   ├── DataSet/                     # Copies utilisées par cette branche
│   ├── Benchmark/                   # Tableaux de résultats
│   ├── outils/                      # Benchmark, conversion et comparaison
│   └── prompt/                      # Prompts de génération directe
├── Par_recomposition/               # Contrainte mémoire (Anthony Hommais)
│   ├── Claude_Opus-4.6/, GPT-5.4/, Qwen-3.6/, ...
│   │                                  # Implémentations et sorties par modèle
│   ├── FCA4J/                       # Référence et jeux de données associés
│   ├── Outils/                      # Pipeline, scripts et configurations
│   │   ├── config/                  # JSON des algorithmes, datasets et runs
│   │   ├── pipeline/                # Exécution, normalisation, comparaison, rapports
│   │   ├── outputs/                 # Runs archivés et métadonnées
│   │   └── Donnees/                 # Notes et synthèses de campagnes
│   ├── Prompt/                      # Prompts et analyses de génération
│   └── TimeRecord/                  # Journaux de mesure
├── Résultats/                       # Synthèses des benchmarks
├── Droit.txt                        # Provenance des jeux et ressources externes
├── FCA_et_LLM.pptx                  # Diapositives de présentation
└── Rapport.pdf                      # Rapport scientifique
```

Les jeux de données racine sont regroupés en fichiers synthétiques `eg9_9` à `eg80_80` et en contextes réels binarisés. Ils sont aussi copiés dans les répertoires propres à FCA4J et aux implémentations afin de satisfaire leurs layouts d’exécution.

Le contrat d’entrée documenté est un CSV dont la première ligne contient les attributs, dont la première colonne identifie les objets et dont les autres cellules sont binaires (`0` ou `1`). Les séparateurs `;` et `,` sont observés ; certains fichiers utilisent des champs guillemetés. La prise en charge exacte dépend toutefois de l’implémentation appelée.

Les sorties sont des graphes Graphviz DOT. Une sortie peut être un treillis induit ou un treillis complet ; la normalisation est donc nécessaire avant certaines comparaisons.

## Prérequis

Aucun fichier `requirements.txt`, `pyproject.toml` ou `setup.py` n’est actuellement déclaré dans le dépôt. Les prérequis doivent donc être installés et vérifiés séparément :

- Python 3 ;
- Java pour le JAR FCA4J `fca4j-cli-0.4.4.jar` ;
- Bash et les commandes Unix utilisées par les scripts (`timeout`, `/usr/bin/time`, `find`, `stat`, `grep`, `awk`, `sed`, `realpath`) ;
- Graphviz `dot` uniquement pour convertir certains DOT en PDF ;
- `/proc` sous Linux pour le suivi des ressources du pipeline ;
- `numpy` et `pandas` pour l’implémentation Gemini 2.5 Pro, lorsque celle-ci est utilisée.

### Installation sous Linux

Pour une distribution Debian ou Ubuntu, les dépendances système peuvent être installées avec :

```bash
sudo apt update
sudo apt install -y \
  python3 python3-pip python3-venv \
  default-jre graphviz \
  bash coreutils findutils grep sed gawk
```

Cette commande installe Python 3, le runtime Java nécessaire à FCA4J, Graphviz et les utilitaires utilisés par les scripts de benchmark et de mesure. Le paquet `default-jre` suffit pour exécuter `fca4j-cli-0.4.4.jar` ; un JDK n’est nécessaire que pour compiler un programme Java.

L’implémentation Gemini 2.5 Pro utilise également `numpy` et `pandas`. Comme aucun fichier de dépendances Python n’est fourni dans le dépôt, ces paquets peuvent être installés séparément dans un environnement virtuel :

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install numpy pandas
```

Les autres scripts Python inspectés utilisent uniquement la bibliothèque standard et ne nécessitent pas de paquet Python supplémentaire.

La génération du code par les modèles nécessite en outre un accès aux modèles ou aux interfaces correspondantes. Cette étape n’est pas reproductible uniquement à partir du dépôt, notamment pour les modèles propriétaires et les usages réalisés via GitHub Copilot.

## Installation et exécution

Les commandes ci-dessous sont celles exposées par les scripts ou les documentations présentes. Elles ne lancent pas de benchmark complet.

### Référence FCA4J

Depuis `Par_recomposition/`, un exemple vérifiable avec les fichiers présents est :

```bash
cd Par_recomposition
java -jar FCA4J/fca4j-cli-0.4.4.jar \
  LATTICE FCA4J/eg9_9/eg9_9.csv \
  -i CSV -s SEMICOLON \
  -g FCA4J/eg9_9/Lattice/eg9_9.dot
```

Le script `FCA4J/fca4j_exec.sh` prend quant à lui un nom de dossier depuis le répertoire FCA4J courant, génère le DOT, puis tente de produire un PDF avec Graphviz. Il faut donc l’utiliser dans une copie de `FCA4J/` qui contient effectivement le dossier du dataset ; la copie `Par_Algo_Direct/FCA4J/` actuelle ne contient que le JAR et le script :

```bash
cd Par_recomposition/FCA4J
./fca4j_exec.sh eg9_9
```

Les chemins de CSV peuvent varier selon la copie du dataset utilisée. Vérifier le layout avant de lancer la commande.

### Benchmark direct

Depuis `Par_Algo_Direct/`, `outils/run_benchmark.sh` attend un fichier exécutable et un dossier de CSV :

```bash
cd Par_Algo_Direct
./outils/run_benchmark.sh <chemin-vers-executable> <dossier-de-CSV>
```

Le script déduit l’interface à un ou deux arguments à partir de motifs textuels présents dans l’aide de l’exécutable, avec un repli heuristique. Cette détection peut échouer avec un autre format d’aide. Il applique une limite de 3 600 secondes, produit un fichier `benchmark_*.txt` et peut tenter une conversion simple virgule-vers-point-virgule en cas d’erreur de parsing. Cette conversion n’est pas un parseur CSV général.

### Mesurer un algorithme de recomposition

Depuis `Par_recomposition/`, `Outils/fast_time.sh` attend exactement deux arguments :

```bash
cd Par_recomposition
./Outils/fast_time.sh <chemin-relatif-vers-algorithme> <nom-du-dataset>
```

Exemples de formes attendues :

```bash
./Outils/fast_time.sh FCA4J/fca4j-cli-0.4.4.jar eg9_9
./Outils/fast_time.sh Claude_Opus-4.6/Python/lattice2.py eg9_9
```

Les journaux sont ajoutés dans `TimeRecord/<dataset>/`.

### Comparer deux treillis

Depuis `Par_recomposition/`, le comparateur utilise uniquement la bibliothèque standard Python :

```bash
cd Par_recomposition
python3 Outils/compare_lattices.py <treillis-1.dot> <treillis-2.dot>
python3 Outils/compare_lattices.py <treillis-1.dot> <treillis-2.dot> --json
python3 Outils/compare_lattices.py <treillis-1.dot> <treillis-2.dot> --simple
```

Les identifiants locaux sont ignorés. Le script compare les signatures canoniques des concepts, puis les arêtes après renumérotation logique. Le code de retour vaut `0` pour une équivalence et `1` pour une différence.

Pour enchaîner la génération FCA4J, l’exécution d’un algorithme Python, la conversion d’un DOT induit en DOT complet et la comparaison, utiliser `fast_compare.sh` :

```bash
cd Par_recomposition
./Outils/fast_compare.sh \
  --fca4j-jar FCA4J/fca4j-cli-0.4.4.jar \
  FCA4J/eg9_9/eg9_9.csv \
  GPT-5.1/lattice.py
```

Le script attend un CSV FCA4J sous `FCA4J/<nom>/<nom>.csv` et un script Python dont les données peuvent être trouvées dans l’un des layouts attendus par l’algorithme. Il produit ou réutilise les DOT dans les répertoires des datasets. Son code de retour vaut `0` pour une équivalence, `1` pour une différence et une valeur supérieure ou égale à `2` pour une erreur d’utilisation, de fichier ou d’exécution.

### Pipeline de recomposition

Depuis `Par_recomposition/`, l’aide et l’exécution du pipeline sont accessibles par :

```bash
cd Par_recomposition
python3 Outils/run_pipeline.py --help
python3 Outils/run_pipeline.py
```

Options utiles :

- `--config-dir` : dossier contenant `algorithms.json`, `datasets.json` et `run.json` ;
- `--run-id` : identifiant explicite du lancement ;
- `--stage all|execution|normalize|compare|report` ;
- `--only-algos` et `--only-datasets` : limiter la sélection ;
- `--resume` : reprendre un répertoire existant ;
- `--continue-on-error` ;
- `--timeout-seconds N` ou `--no-timeout`.

Un lancement écrit dans `Outils/outputs/<run_id>/` :

- `execution/` : journaux, métadonnées et DOT copiés ;
- `normalize/` : DOT complets normalisés ;
- `compare/` : rapports JSON par paire ;
- `report/rapport_pipeline.md` : synthèse ;
- `metadata/` : configuration, index d’étapes et résumé.

Le pipeline peut continuer après une erreur lorsque `continue_on_error` est actif. Une étape marquée comme exécutée ne signifie donc pas que tous les cas ont produit une sortie comparable.

## Évaluation et interprétation

FCA4J `0.4.4` sert d’oracle expérimental pour générer une référence sur le même contexte formel. Le protocole distingue :

- **validité syntaxique** : le programme s’exécute et produit un fichier DOT exploitable ;
- **validité fonctionnelle** : les données et le format d’entrée-sortie sont traités conformément au contrat ;
- **correction structurelle** : concepts et relations de couverture sont équivalents à FCA4J.

`induced_to_full_dot.py` reconstruit les informations complètes lorsque l’algorithme ne produit qu’un treillis induit. La conversion vérifie notamment l’acyclicité, les cardinalités, la monotonie et l’existence d’un unique sommet et d’un unique fond. Une sortie peut donc échouer avant la comparaison sans que cela prouve à lui seul la cause algorithmique de l’écart.

Le comparateur ne compare pas le texte brut des DOT : deux fichiers peuvent différer par la numérotation ou l’ordre d’énumération tout en décrivant le même treillis. Il compare les signatures des concepts et les arêtes normalisées. Les résultats `false` peuvent toutefois correspondre à une différence réelle, à une sortie mal formée ou à une normalisation impossible ; les rapports détaillés doivent être consultés.

## Résultats principaux

### Génération directe

Le tableau [Benchmark direct](Résultats/Benchmark_Algo_Direct.md) contient 16 datasets et sépare le temps, le pic RAM, la taille de sortie et l’équivalence à FCA4J. Quelques résultats représentatifs :

| Dataset | Modèle | Temps | RAM max | Équivalence |
|---|---|---:|---:|---|
| `eg40_40` | FCA4J | 1,26 s | N/A dans le tableau | Oui, référence |
| `eg40_40` | Claude Sonnet 4.6 | 40,72 s | 55 MB | Oui |
| `eg40_40` | ChatGPT 5.3 Codex | 48,02 s | 12 MB | Oui |
| `eg40_40` | Gemini 3.1 | 4 min 32,85 s | 10 MB | Oui |
| `eg40_40` | Qwen | 1 min 24,59 s | 18 MB | Non |
| `eg50_50` | Claude Sonnet 4.6 | 13 min 18,97 s | 898 MB | Oui |
| `eg50_50` | ChatGPT 5.3 Codex | Timeout | N/A | Non |
| `eg50_50` | Gemini 3.1 | Timeout | N/A | Non |
| `eg50_50` | Qwen | 25 min 44,04 s | 72 MB | Non |

Ces valeurs appartiennent à la campagne directe et ne doivent pas être mélangées avec celles du pipeline de recomposition.

### Campagne avec contrainte mémoire

Le rapport [Benchmark avec restriction de mémoire](Résultats/Benchmark_avec_restriction_de_mémoire.md) indique, pour la campagne archivée du 10 mai 2026 : 119 exécutions, 119 normalisations, 81 paires comparées et 5 timeouts, avec une limite configurée à 900 secondes.

Les pics RSS maximum rapportés sur les 17 cas de chaque algorithme sont :

| Algorithme | Pic RSS | Observation |
|---|---:|---|
| FCA4J | 845,99 MiB | Référence ; pic élevé sur cette campagne |
| Claude `lattice2` | 107,52 MiB | Treillis normalisés et comparés sur les cas archivés |
| GPT-5.3 Codex | 34,00 MiB | Plusieurs échecs sur les datasets réels et timeout sur `eg50_50` |
| GPT-5.4 memory-aware | 129,96 MiB | Exécutions terminées sur plusieurs synthétiques, sorties réelles souvent non comparables |
| Gemini 3.1 | 1,42 GiB | Plusieurs timeouts et échecs de conversion |
| Kimi K2 | 127,42 MiB | Échecs de conversion liés au format de label dans le rapport |
| Qwen 3.6 | 22,28 MiB | Plusieurs sorties normalisées ; couverture incomplète selon les datasets |

Ces nombres sont des maxima observés, pas des moyennes. Le rapport mesure principalement le temps écoulé et la RSS du processus ; d’autres colonnes mesurent des écritures ou la taille de répertoires surveillés. Elles ne sont pas directement interchangeables avec le temps CPU et les tailles du benchmark direct.

## Limites connues

- Le nombre de concepts peut croître combinatoirement avec la taille et la structure du contexte.
- Les relations de couverture sont plus difficiles à reconstruire que les concepts eux-mêmes.
- Les implémentations générées peuvent être rapides tout en produisant un treillis incorrect ou un DOT impossible à normaliser.
- Les algorithmes n’implémentent pas tous réellement les stratégies mémoire suggérées par les prompts.
- Les résultats varient selon le modèle, le prompt, le dataset et le protocole d’exécution.
- Les campagnes directes et recomposées utilisent des outils et des métriques différents.
- Le pipeline sélectionne parfois le DOT le plus récent ; un artefact préexistant peut influencer la sortie si un algorithme ne nettoie pas ses fichiers.
- Les mesures disque peuvent inclure des fichiers préexistants dans le dossier surveillé, et `total_written_bytes` repose sur la métrique `wchar` observée.
- `eg80_80` est présent dans la configuration des datasets, mais un DOT FCA4J archivé est signalé comme vide dans la documentation d’entrée-sortie.
- La reproduction de la génération initiale dépend d’interfaces de modèles et de versions qui ne sont pas toutes archivées dans le dépôt.

## Auteurs et contributions

- **Corentin Fay** : génération directe d’algorithmes, prompts, exécutions et benchmark dans `Par_Algo_Direct/`.
- **Anthony Hommais** : génération sous contrainte mémoire, scripts de recomposition, pipeline de comparaison, sorties et analyses dans `Par_recomposition/`.

Les deux contributions étudient la même question de recherche avec un protocole commun de comparaison structurelle, mais leurs campagnes de mesures doivent être lues séparément.

## Références et ressources externes

Les ressources sont attribuées selon [Droit.txt](Droit.txt) et les documents du projet :

- **FCA4J**, outil de référence et de génération de treillis : [site du LIRMM](https://www.lirmm.fr/fca4j/) et [dépôt du benchmark](https://gite.lirmm.fr/gutierre/fca4j-benchmark), associé à Alain Gutierrez dans les documents consultés ;
- **Jeux de données synthétiques**, issus du dépôt du groupe précédent : [TER-M1--Code-and-Test-sets](https://github.com/OskrJF/TER-M1---Code-and-Test-sets/tree/main/Synthetics), attribué dans `Droit.txt` à Valentino Cocks, Arame Diop, Oscar Jimenez Flores et Yazmín Mendoza ;
- références bibliographiques et ressources théoriques complémentaires : voir les sections correspondantes du [rapport scientifique](Rapport.pdf).

## Documents complémentaires

- [Rapport scientifique](Rapport.pdf) : théorie, protocole, prompts, résultats, menaces à la validité et perspectives ;
- [Diapositives de présentation](FCA_et_LLM.pptx) : synthèse pédagogique et résultats mis en avant à l’oral ;
- [Benchmark direct](Résultats/Benchmark_Algo_Direct.md) ;
- [Benchmark avec restriction de mémoire](Résultats/Benchmark_avec_restriction_de_mémoire.md) ;
- [Tableau détaillé de la branche directe](Par_Algo_Direct/Benchmark/Tableau_finaux.md) ;
- documentation du pipeline dans `Par_recomposition/Documentation/` et `Par_recomposition/Outils/Documentation/` ;
- jeux de données dans `Dataset/` et copies propres aux deux branches.
