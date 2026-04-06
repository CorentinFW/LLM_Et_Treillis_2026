# Rôle
Tu es un expert en Bash scripting, systèmes Linux/Unix, génie logiciel et robustesse CLI.

# Contexte
On travaille dans un dépôt Linux contenant notamment :
- un dossier `TimeRecord/` pour stocker les résultats d’exécution ;
- un wrapper `Outils/run_with_cpu_time.py` utilisé pour mesurer le temps CPU lors de l’exécution d’un script Python ;
- des algorithmes fournis soit via :
  - un JAR (cas FCA4J),
  - soit un script Python (cas “LLM/*/Python/*.py” ou “GPT-5.1/*.py”).

Le script Bash à générer doit lancer un algorithme sur un CSV et journaliser proprement la sortie dans `TimeRecord/`.

# Objectif
Génère un script Bash exécutable et maintenable (un seul fichier `.sh`) qui :

1) Prend exactement 2 arguments positionnels obligatoires :
   - `<path_vers_algo>` : chemin relatif (depuis la racine du dépôt) vers l’algorithme à exécuter (fichier `.jar` ou `.py`).
   - `<Nom_du_csv>` : nom du dataset (ex: `eg20_20`, `balance-scale_binarized`).

2) Construit automatiquement les chemins d’entrée/sortie à partir de ces arguments.

3) Exécute l’algorithme sur le CSV correspondant.

4) Écrit (en ajout/append) les logs complets (stdout + stderr) dans :
   - `TimeRecord/<Nom_du_csv>/<Nom_du_premier_dossier_parent_donné_dans_le_path>_result.txt`

   Où `<Nom_du_premier_dossier_parent_donné_dans_le_path>` est le premier composant du chemin `<path_vers_algo>` (ex: `Claude_Opus-4.6` dans `Claude_Opus-4.6/Python/lattice2.py`, `FCA4J` dans `FCA4J/fca4j-cli-0.4.4.jar`).

# Informations d’entrée attendues
Le script doit accepter :
- `./fast_time.sh <path_vers_algo> <Nom_du_csv>`

Exemples de valeurs d’entrée :
- `<path_vers_algo>` = `FCA4J/fca4j-cli-0.4.4.jar`
- `<path_vers_algo>` = `Claude_Opus-4.6/Python/lattice2.py`
- `<Nom_du_csv>` = `balance-scale_binarized`
- `<Nom_du_csv>` = `eg9_9`

# Contraintes techniques
Respecte impérativement ces contraintes :

## Qualité et robustesse
- Utiliser un mode strict : `set -euo pipefail` (ou justifier précisément toute exception).
- Quoter systématiquement les variables (éviter word-splitting/globbing involontaire).
- Ne jamais utiliser de pratiques dangereuses (pas de `eval`, pas de suppression non ciblée, pas de `rm -rf` sur des chemins non validés).
- Messages d’erreur clairs sur `stderr` + code de sortie non nul.
- Validation des arguments (nombre, non-vide, types attendus `.jar`/`.py`, fichiers existants).
- Créer les dossiers de sortie avec `mkdir -p`.
- Script compatible environnement Linux standard (Bash 4+). Éviter les dépendances non standard.

## Résolution de la racine du dépôt
Le script doit fonctionner même s’il est lancé depuis un répertoire quelconque.
- Déterminer `REPO_ROOT` de manière robuste : partir du répertoire du script (`BASH_SOURCE[0]`) puis remonter jusqu’à trouver un dossier contenant `Outils/` ET `TimeRecord/`.
- Si introuvable, afficher une erreur expliquant où se placer / comment corriger.

## Détection du “type d’algo”
- Si `<path_vers_algo>` se termine par `.jar` (ou si le premier dossier parent vaut `FCA4J`), exécuter en mode “FCA4J”.
- Si `<path_vers_algo>` se termine par `.py`, exécuter en mode “Python”.
- Sinon : erreur explicite.

## Chemins de CSV (règles)
Le script doit construire le chemin du CSV `CSV_PATH` à partir de `<Nom_du_csv>` et du “parent” :
- Cas FCA4J (JAR) :
  - `CSV_PATH="${REPO_ROOT}/FCA4J/<Nom_du_csv>/<Nom_du_csv>.csv"`
- Cas Python (script `.py`) :
  - Tenter d’abord : `"${REPO_ROOT}/<Parent>/Python/<Nom_du_csv>/<Nom_du_csv>.csv"`
  - Sinon tenter : `"${REPO_ROOT}/<Parent>/<Nom_du_csv>/<Nom_du_csv>.csv"`
  - Si aucun n’existe : erreur + suggestion.

## Commandes à produire (référence)
Le script final doit reproduire cette logique d’exécution :

### FCA4J (JAR)
Commande de référence (exemple) :
`java -jar FCA4J/fca4j-cli-0.4.4.jar LATTICE FCA4J/balance-scale_binarized/balance-scale_binarized.csv -i CSV -s SEMICOLON -g FCA4J/balance-scale_binarized/Lattice/balance-scale_binarized.dot >> TimeRecord/balance-scale_binarized/FCA4J_result.txt`

Dans le script :
- Construire `DOT_OUT="${REPO_ROOT}/FCA4J/<Nom_du_csv>/Lattice/<Nom_du_csv>.dot"`.
- Créer le dossier `$(dirname "$DOT_OUT")` si nécessaire.
- Exécuter :
  - `java -jar "$ALGO_PATH" LATTICE "$CSV_PATH" -i CSV -s SEMICOLON -g "$DOT_OUT"`
- Journaliser stdout+stderr dans le fichier résultat.

### Python (script `.py`)
Commande de référence (exemple) :
`python3 Outils/run_with_cpu_time.py Claude_Opus-4.6/Python/lattice2.py Claude_Opus-4.6/Python/eg9_9/eg9_9.csv >> TimeRecord/eg20_20/Claude_Opus-4.6_result.txt 2>&1`

Dans le script :
- Utiliser le wrapper :
  - `python3 "${REPO_ROOT}/Outils/run_with_cpu_time.py" "$ALGO_PATH" "$CSV_PATH"`
- Journaliser stdout+stderr dans le fichier résultat.

# Instructions à suivre
Génère le script Bash complet en respectant strictement :

1) En-tête
- Shebang obligatoire : `#!/usr/bin/env bash`
- Commentaires en tête décrivant : but, usage, exemples.

2) Structure du code
- Code lisible, noms explicites.
- Utiliser des fonctions si utile, par exemple :
  - `usage()`
  - `die()`
  - `require_cmd()`
  - `find_repo_root()`
  - `detect_algo_kind()`
  - `build_paths()`
  - `run_fca4j()` / `run_python()`

3) UX CLI
- À chaque exécution, afficher des messages d’info (sur `stderr` ou `stdout`) indiquant :
  - algo détecté, chemins calculés, fichier de log.
- Écrire aussi un petit en-tête dans le fichier log (date, commande lancée, etc.).

4) Gestion des erreurs
- Validation :
  - nombre d’arguments = 2 ;
  - `ALGO_PATH` existe ;
  - `Nom_du_csv` non vide ;
  - `CSV_PATH` existe ;
  - dépendances : `java` si JAR, `python3` si Python.
- Utiliser `trap` pour signaler proprement la ligne en erreur (facultatif mais recommandé).

5) Journalisation
- Toujours faire de l’append (`>>`) dans le fichier résultat.
- Capturer `stderr` dans le log : `>>"$OUT_FILE" 2>&1`.

6) Portabilité
- Éviter GNU-only superflus quand possible.
- Ne pas supposer que l’utilisateur a lancé le script depuis la racine.

7) Interdictions
- Ne pas produire plusieurs fichiers.
- Ne pas ajouter d’options CLI non demandées.
- Ne pas proposer de “pages”, d’UI, ou de fonctionnalités bonus.

8) Auto-vérification avant réponse
Avant de rendre le script, vérifie mentalement et corrige si besoin :
- `set -euo pipefail` et quoting correct ;
- erreurs gérées (messages + exit code) ;
- commentaires clairs ;
- robustesse aux entrées incorrectes ;
- chemins de sortie conformes à `TimeRecord/<Nom_du_csv>/<Parent>_result.txt`.

# Format de sortie attendu
Tu dois répondre avec :
- Un unique bloc de code Bash (Markdown) contenant le script complet, prêt à être exécuté.
- Aucun texte hors du bloc de code.
