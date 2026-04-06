# Pistes de comparaison des algorithmes de calcul de treillis

## Introduction des pistes de comparaison explorées

### Clarification et précision du besoin
Pour rendre la comparaison exploitable dans ce projet, on peut reformuler l'objectif ainsi :

1. Comparer les **3 implémentations cibles** sur des critères complémentaires :
   - FCA4J (CLI 0.4.4, commande `LATTICE`, algorithme `ADD_EXTENT` par défaut)
   - `Claude_Opus-4.6/Python/lattice2.py`
   - `GPT-5.3-Codex/Python/lattice.py`
2. Distinguer :
   - la **validité mathématique** du treillis (mêmes concepts et mêmes arêtes)
   - l'**efficacité** (CPU/temps, mémoire, I/O)
   - la **robustesse d'exploitation** (stabilité, reprise, paramétrage)
3. Éviter une métrique unique : un algorithme peut être meilleur en vitesse mais moins bon en mémoire, ou inversement.

### Ce qui est déjà disponible dans le dépôt (faisabilité validée)
Les comparaisons proposées ci-dessous sont directement utilisables car le dépôt contient déjà :

- génération de treillis FCA4J en DOT via `fca4j-cli-0.4.4.jar`
- génération Python (Claude et GPT)
- mesure CPU via `Outils/run_with_cpu_time.py`
- orchestration de timings via `Outils/fast_time.sh`
- comparaison de treillis DOT par signatures canoniques via `Outils/compare_lattices.py`
- conversion DOT induit -> DOT complet via `Outils/induced_to_full_dot.py`
- historiques de mesures dans `TimeRecord/*`

---

## Modèle 1 - Équivalence structurelle du treillis (exactitude)

### Manière de comparer
Comparer les sorties DOT de deux algorithmes au niveau logique (concepts + arêtes), indépendamment de la numérotation des nœuds.

Protocole :
1. Générer les deux DOT à comparer sur le même dataset.
2. Si l'un des DOT est en représentation induite/réduite, le convertir en DOT complet avec `induced_to_full_dot.py`.
3. Utiliser `compare_lattices.py` pour vérifier :
   - signatures de concepts présentes/absentes
   - ambiguïtés de signature
   - différences d'arêtes normalisées
4. Conclure équivalent / différent.

### Pourquoi c'est intéressant
- C'est le critère principal de correction FCA : deux algorithmes doivent produire le même treillis (à isomorphisme de noms locaux près).
- Évite les faux écarts dus aux conventions d'affichage (ordre des labels, id internes).
- Permet d'identifier rapidement où se situe une divergence : nœuds manquants, arêtes en trop, ambiguïtés.

### Documentation scientifique si existante
- B. Ganter, "Two Basic Algorithms in Concept Analysis" (1984) : fondements d'énumération correcte des concepts fermés (NextClosure).
- B. Ganter, R. Wille, *Formal Concept Analysis: Mathematical Foundations* (1999) : définition du treillis des concepts, unicité structurelle.

### Modèles possibles d'implémentation dans ce projet
- Réutiliser `Outils/fast_compare.sh` pour une chaîne automatisée (génération, conversion full, comparaison).
- Produire un rapport JSON (`compare_lattices.py --json`) et l'archiver par dataset dans `TimeRecord/<dataset>/`.
- Définir une règle : une expérience n'est validée que si l'équivalence structurelle avec la référence FCA4J est vraie.

---

## Modèle 2 - Performance CPU / temps d'exécution

### Manière de comparer
Comparer le coût temporel par dataset, en distinguant :
- CPU process (mesuré par `run_with_cpu_time.py`)
- durée rapportée par le moteur (ex. `duration` FCA4J)

Protocole :
1. Pour chaque dataset, lancer chaque algorithme avec `Outils/fast_time.sh`.
2. Répéter N fois (ex. N=5) pour lisser la variance.
3. Extraire médiane, min, max, écart relatif.
4. Tracer par dataset et par famille de datasets (`eg9_9` -> `eg80_80`, datasets réels binarisés).

### Pourquoi c'est intéressant
- Mesure directe de la valeur opérationnelle.
- Fait ressortir les points forts selon la taille/structure des données.
- Permet de distinguer un algorithme "rapide en petit" d'un algorithme "robuste en grand".

### Documentation scientifique si existante
- La complexité de l'énumération des concepts dépend du nombre de concepts, potentiellement exponentiel en pire cas (résultat classique FCA).
- Les comparaisons empiriques sont standard en FCA pour départager les algorithmes sur des classes de contextes différentes.

### Modèles possibles d'implémentation dans ce projet
- S'appuyer sur les logs existants `TimeRecord/*/*_result.txt`.
- Ajouter un parseur simple (ultérieurement) pour agréger les lignes `CPU time (self)` et `duration`.
- Sortie attendue : tableau synthèse (dataset x algo) + classement par médiane.

---

## Modèle 3 - Scalabilité (croissance avec |G|, |M| et densité)

### Manière de comparer
Comparer le comportement de croissance plutôt que le temps brut :
- évolution du temps quand on passe de `eg9_9` à `eg80_80`
- croissance du nombre de concepts et d'arêtes
- sensibilité à la densité binaire du contexte

Protocole :
1. Utiliser la série synthétique `eg*_*` pour la montée en taille.
2. Relever pour chaque run :
   - |G|, |M|
   - nombre de concepts
   - nombre d'arêtes
   - CPU/temps
3. Calculer des ratios :
   - temps / concept
   - temps / arête
   - pente log-log approximative

### Pourquoi c'est intéressant
- Désigne les points forts structurels des approches, pas seulement un score ponctuel.
- Permet de choisir un algorithme selon le régime d'usage cible (petits, moyens, grands contextes).

### Documentation scientifique si existante
- En FCA, la taille du treillis peut exploser combinatoirement ; la scalabilité est donc un axe central d'évaluation algorithmique.
- Les profils de performance dépendent fortement de la structure du contexte (densité, corrélations attributaires).

### Modèles possibles d'implémentation dans ce projet
- Réutiliser les jeux `eg9_9`, `eg20_20`, `eg30_30`, `eg40_40`, `eg50_50`, `eg80_80` déjà présents.
- Exploiter les compteurs déjà affichés par les scripts Python (concepts/arêtes) et les sorties FCA4J.
- Produire des courbes dans un notebook ou un script de post-traitement dans `Outils/Documentation/`.

---

## Modèle 4 - Coût mémoire et coût disque (I/O)

### Manière de comparer
Mesurer l'empreinte mémoire et le volume I/O pendant le calcul.

Observation de code utile :
- `Claude_Opus-4.6/Python/lattice2.py` : partitionnement JSON puis rechargement global en mémoire pour calcul des arêtes.
- `GPT-5.3-Codex/Python/lattice.py` : partitionnement + ingestion SQLite + calcul d'arêtes via requêtes indexées (approche orientée disque).
- FCA4J : implémentation Java configurable (`-m` BITSET/ROARING_BITMAP/etc.), exécution monolithique en JVM.

Protocole :
1. Mesurer mémoire max RSS et temps (ex. `/usr/bin/time -v` autour des commandes).
2. Mesurer taille des artefacts intermédiaires (`partition/`, `.sqlite`, `.jsonl`, DOT final).
3. Comparer par dataset la courbe "temps vs mémoire".

### Pourquoi c'est intéressant
- Permet de valoriser les approches sobres en RAM.
- Révèle les compromis : plus de disque peut réduire le pic mémoire.
- Critique pour grands contextes et machines contraintes.

### Documentation scientifique si existante
- Les représentations bitset/bitmap et les stratégies external-memory sont des leviers classiques pour la fouille de structures combinatoires massives.
- En pratique FCA, les compromis mémoire-I/O sont déterminants quand le nombre de concepts devient élevé.

### Modèles possibles d'implémentation dans ce projet
- Ajouter une variante de `fast_time.sh` qui encapsule la commande dans `/usr/bin/time -v`.
- Archiver `Maximum resident set size` + tailles de fichiers intermédiaires dans `TimeRecord/<dataset>/`.
- Pour FCA4J, tester plusieurs `-m` (`BITSET`, `ROARING_BITMAP`, etc.) sur un sous-ensemble de datasets.

---

## Modèle 5 - Robustesse et résilience d'exécution

### Manière de comparer
Comparer la capacité à finir correctement sous contraintes (temps, mémoire, erreurs d'entrée).

Protocole :
1. Exécuter avec timeout contrôlé (FCA4J dispose de `-timeout`).
2. Injecter des cas limites :
   - CSV vide / mal formé
   - séparateur incorrect
   - datasets plus denses
3. Mesurer :
   - taux de succès
   - qualité des messages d'erreur
   - possibilité de reprise partielle (artefacts intermédiaires exploitables)

### Pourquoi c'est intéressant
- Un algorithme rapide mais fragile est difficile à industrialiser.
- La robustesse est un vrai point fort en contexte expérimental long.

### Documentation scientifique si existante
- Peu de "théorie" spécifique ; c'est un axe de génie logiciel expérimental (fiabilité, observabilité, reprise).

### Modèles possibles d'implémentation dans ce projet
- Créer une matrice de scénarios de panne par dataset.
- Réutiliser les logs verboses (`-v` FCA4J, logs Python existants).
- Noter un score de robustesse : succès, explicabilité des erreurs, récupération.

---

## Modèle 6 - Déterminisme et reproductibilité

### Manière de comparer
Comparer la stabilité des sorties à entrées identiques :
- même nombre de concepts/arêtes
- même structure logique (équivalence)
- même DOT binaire (si tri déterministe)

Protocole :
1. Relancer K fois chaque algo sur un même dataset.
2. Comparer hash des DOT et/ou comparer structure avec `compare_lattices.py`.
3. Vérifier la stabilité des métriques temporelles (dispersion faible ou non).

### Pourquoi c'est intéressant
- Essentiel pour une étude scientifique reproductible.
- Permet d'isoler les non-déterminismes dus à l'ordre d'itération, au hash, ou à la concurrence.

### Documentation scientifique si existante
- Reproductibilité expérimentale : exigence méthodologique standard en évaluation d'algorithmes.

### Modèles possibles d'implémentation dans ce projet
- Conserver toutes les répétitions dans `TimeRecord/` avec horodatage.
- Ajouter un hash SHA-256 des DOT générés dans les logs.
- En cas de divergence, analyser via `compare_lattices.py --json`.

---

## Modèle 7 - Sensibilité aux paramètres et tuning

### Manière de comparer
Comparer chaque algorithme après réglage raisonnable de ses paramètres.

Paramètres observables :
- FCA4J : `-m <impl>`, `-a`, `-d`, `-timeout`
- Claude : batch adaptatif, `CHUNK_SIZE`, partitionnement
- GPT-5.3-Codex : nombre de partitions, chunk size, groupement d'ingestion SQLite, intervalle de progression

Protocole :
1. Choisir une grille de paramètres compacte.
2. Mesurer gain/perte par rapport au profil par défaut.
3. Identifier les paramètres réellement influents.

### Pourquoi c'est intéressant
- Met en évidence le potentiel réel de chaque approche.
- Évite les comparaisons injustes (default A vs default B).

### Documentation scientifique si existante
- En benchmark algorithmique, l'analyse de sensibilité est une pratique standard pour distinguer performance intrinsèque et performance due au tuning.

### Modèles possibles d'implémentation dans ce projet
- Définir un protocole "baseline + tuning léger".
- Conserver la configuration exacte de chaque run dans les logs (déjà partiellement fait dans `fast_time.sh`).
- Rapporter un score final avec et sans tuning.

---

## Avis complet sur la pertinence de chaque manière de comparer et leurs interactions

### Pertinence individuelle
1. **Équivalence structurelle** : indispensable. Sans elle, les autres métriques n'ont pas de sens.
2. **Performance CPU/temps** : très pertinente pour la décision pratique, mais doit être lue avec l'exactitude.
3. **Scalabilité** : cruciale pour projeter l'usage futur ; plus informative qu'un seul benchmark.
4. **Mémoire/I-O** : très pertinente dans ce projet, car les implémentations Python diffèrent précisément sur ce compromis.
5. **Robustesse** : importante pour l'exploitation continue, surtout sur gros jeux.
6. **Reproductibilité** : nécessaire pour une comparaison scientifique crédible.
7. **Sensibilité paramètres** : utile pour mettre en avant le meilleur potentiel de chaque approche.

### Intérêt entre elles (complémentarité)
- Exactitude + Performance : combinaison minimale pour conclure "meilleur" sans biais.
- Scalabilité + Mémoire/I-O : explique *pourquoi* un algo gagne/perd selon les tailles.
- Robustesse + Reproductibilité : sécurise la confiance dans les résultats.
- Tuning + Performance : sépare la qualité de l'algorithme et la qualité des paramètres par défaut.

### Désintérêt / limites entre elles
- Performance seule est insuffisante si les treillis diffèrent.
- Mémoire seule peut favoriser un algo trop lent pour un usage réel.
- Tuning trop large peut devenir coûteux et brouiller l'analyse principale.
- Comparer des DOT non normalisés (induit vs full) peut conduire à de faux écarts.

### Recommandation synthétique (ordre d'adoption)
1. Mettre en place un pipeline systématique **exactitude -> performance -> scalabilité**.
2. Ajouter ensuite **mémoire/I-O** pour les datasets moyens/grands.
3. Terminer par **robustesse**, **reproductibilité**, puis **tuning** sur les cas critiques.

Ce séquencement permet d'identifier rapidement les points forts de chaque algorithme tout en gardant une méthode fiable, reproductible et exploitable dans votre projet.
