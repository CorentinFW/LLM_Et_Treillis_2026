# Rôle

Tu es un expert en **Python**, en **mesure de performance**, et en **génie logiciel** (robustesse, maintenabilité, compatibilité).

# Contexte

On dispose déjà d’un ou plusieurs algorithmes Python **fonctionnels** dans un dépôt. On doit **ajouter une fonctionnalité** : afficher **à la fin de l’exécution** le **temps CPU** consommé par l’algorithme.

Important : le temps demandé est le **temps CPU** (temps de calcul effectif), **pas** le temps « horloge » (wall-clock).

# Objectif

Implémente une solution qui :

1. mesure le **temps CPU** consommé pendant l’exécution de l’algorithme ;
2. affiche ce temps **en fin de processus** (ou en `finally` si une erreur survient) ;
3. n’altère pas le comportement fonctionnel de l’algorithme (mêmes sorties, mêmes fichiers produits, à l’exception d’une ligne de timing ajoutée à la fin).

# Contraintes (impératives)

- Ne modifie **aucun fichier existant** de l’algorithme (pas d’édition, pas de refactor, pas d’ajout de print dans l’algo).
- N’ajoute pas de dépendances externes : utilise uniquement la **bibliothèque standard** Python.
- Mesure un **temps CPU**, pas un temps système/wall-clock :
  - privilégie `time.process_time()` (CPU du processus courant) ;
  - sur Linux/macOS, si pertinent, tu peux aussi exploiter `resource.getrusage` pour exposer `user` + `sys`.
- La solution doit être **simple à utiliser** (commande unique) et **portable** (au minimum Linux).
- La solution doit être **robuste** : le temps doit s’afficher même si l’algorithme termine avec une exception (utilise `try/finally` ou `atexit`).
- N’invente pas d’API de l’algorithme : adapte-toi à l’existant.

# Hypothèses et limites (à traiter explicitement)

- Si l’algorithme lance des **sous-processus** (multiprocessing / subprocess), `time.process_time()` ne mesure que le CPU du processus courant. Dans ce cas :
  - sur Linux, propose une option qui **additionne** `RUSAGE_SELF` et `RUSAGE_CHILDREN` (si disponible) ;
  - sinon, documente clairement la limite.

# Étapes à suivre (méthode)

1. **Identifier le point d’entrée** de l’algorithme sans le modifier :
   - cas A : l’algo est un script lancé via `python path/to/algo.py ...` ;
   - cas B : l’algo s’exécute via un module (`python -m package.module ...`) ;
   - cas C : l’algo expose une fonction `main()` importable.

2. Choisir l’approche la plus sûre **sans modifier l’algo** :
   - approche recommandée : écrire un **wrapper** `run_with_cpu_time.py` qui exécute l’algo « comme en CLI » via `runpy` (pour A/B), ou via import (pour C).

3. Implémenter la mesure CPU :
   - capturer les timestamps CPU avant/après (`process_time()` et/ou `resource.getrusage`) ;
   - afficher un récapitulatif unique à la fin, formaté proprement.

4. Vérifier que l’exécution « wrapper → algo » conserve :
   - les arguments CLI (`sys.argv`) ;
   - le répertoire de travail si nécessaire ;
   - le code retour (si l’algo l’utilise).

# Exigences de conception (génie logiciel)

- Code modulaire :
  - une fonction de mesure (ex. `measure_cpu_time(callable)` ou un context manager) ;
  - une fonction d’exécution du point d’entrée (ex. `run_script(path, argv)` / `run_module(name, argv)`).
- Lisibilité : noms explicites, messages d’erreur clairs.
- Pas de logique inutile : rester minimal.

# Format de sortie attendu

Tu dois produire :

1. Les **fichiers ajoutés** (chemins + contenu) nécessaires pour activer la fonctionnalité sans modifier l’existant.
2. Une section **"Commande d’exécution"** montrant exactement comment lancer l’algorithme via le wrapper.
3. Une section **"Détails de mesure"** expliquant brièvement :
   - quelle API est utilisée (`time.process_time`, éventuellement `resource.getrusage`) ;
   - ce que mesure exactement le temps CPU ;
   - la limite éventuelle concernant les sous-processus.

## Format d’affichage (timing)

Affiche une ligne unique à la fin, par exemple :

- `CPU time (self): 1.234567 s`
- (optionnel si supporté) `CPU time (children): 0.123456 s` et `CPU time (total): 1.358023 s`

# Questions de clarification (si nécessaire)

Si tu ne peux pas déterminer de façon fiable comment lancer l’algorithme, pose **au maximum 3 questions** très ciblées (ex. commande actuelle, script/module d’entrée, arguments typiques). Sinon, n’en pose aucune et implémente directement.
