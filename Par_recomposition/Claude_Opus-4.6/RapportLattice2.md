# Rapport d’analyse — `Python/lattice2.py` (niveau avancé)

## 1) Objectif du code

- **Objectif principal** : calculer le **treillis des concepts formels** (FCA) d’un contexte binaire (CSV) et produire son **diagramme de Hasse** au format **DOT**, en limitant la consommation mémoire.
- **Problème / cas d’usage** : énumérer tous les concepts formels (intents fermés + extents associés) via **NextClosure**, puis calculer la relation de couverture pour dessiner le treillis.
- **Entrées / sorties observées** :
  - Entrée certaine : un fichier CSV binaire (`;`, première ligne = attributs, première colonne = objets).
  - Sorties certaines :
    - création temporaire d’un répertoire `partition/` au même niveau que le CSV (écritures JSON par chunks), puis suppression en fin de run.
    - écriture d’un DOT : `<csv_dir>/Lattice/<basename>_LLM_2.dot`.

## 2) Vue d’ensemble

### Architecture logique

- **Fichier unique** : tout est dans `lattice2.py`.
- **Pipeline** :
  1) parse CSV → structures bitmask
  2) énumération des concepts (NextClosure) → partitions sur disque
  3) relecture + fusion + déduplication → liste globale de concepts en RAM
  4) calcul des arêtes de couverture (Hasse)
  5) calcul des labels “propres” (réduction) + génération DOT

### Responsabilités majeures (qui fait quoi)

- **I/O CSV** : `load_context()`
- **Opérateurs FCA** : `prime_attrs()`, `prime_objs()`, `closure()`
- **Énumération lectique** : `next_closure()`
- **Partitionnement / stockage intermédiaire** : `next_closure_partition()`, `save_partition()`
- **Recomposition** : `load_partitions()`
- **Couverture (Hasse)** : `compute_edges()` (avec index par niveaux)
- **Réduction des labels** : `compute_own_labels()`
- **Rendu DOT** : `write_dot()`
- **Point d’entrée CLI** : `main()`

### Points d’entrée et dépendances externes

- **Point d’entrée** : `main()` via `if __name__ == "__main__":`.
- **Dépendances** : uniquement bibliothèque standard (`csv`, `os`, `json`, `gc`, `sys`, `shutil`).
- **Dépendance OS** : `get_available_memory_mb()` lit `/proc/meminfo` (spécifique Linux) avec fallback conservateur.
- **Fichiers** : lecture du CSV, écritures JSON dans `partition/partX/chunkY.json`, écriture du DOT final.

## 3) Fonctionnement détaillé

### Schéma du flux d’exécution (exécution mentale)

1. `main()`
2. Validation du chemin CSV, calcul des chemins de sortie (`Lattice/..._LLM_2.dot`) et de travail (`partition/`).
3. `load_context(csv_path)` → `objects`, `attributes`, `obj_attrs`, `attr_objs`, tailles.
4. Initialisation des masques universels : `all_objs`, `all_attrs`.
5. Détermination d’une taille de batch : `compute_adaptive_batch_size()`.
6. `next_closure_partition(...)` :
   - calcule le premier concept `closure(∅)`
   - boucle `next_closure()` jusqu’à épuisement
   - écrit des partitions sur disque via `save_partition()`
7. `load_partitions(...)` : recharge tous les chunks JSON, convertit en bitmasks, déduplique, trie.
8. `compute_edges(concepts)` : calcule les arêtes de couverture (child → parent).
9. `write_dot(...)` : calcule les labels propres, écrit les nœuds + arêtes au format DOT.
10. Nettoyage : suppression de `partition/`.

### Bloc : `load_context(csv_path)`

- **Rôle** : parser le CSV et construire une représentation compacte du contexte.
- **Données manipulées** :
  - `objects: list[str]`, `attributes: list[str]`
  - `obj_attrs: list[int]` (bitmask d’attributs par objet)
  - `attr_objs: list[int]` (bitmask d’objets par attribut)
- **Étapes clés** :
  1. lire l’en-tête, extraire les attributs
  2. pour chaque ligne objet : construire `mask` (bits attributs à 1)
  3. construire `attr_objs` en parcourant les bits de chaque `obj_attrs[g]`
- **Interactions** : alimente tous les calculs FCA (`closure`, `NextClosure`).

### Bloc : `prime_attrs()`, `prime_objs()`, `closure()`

- **Rôle** : implémenter les opérateurs $X'$, $Y'$, $X''$.
- **Données** : bitmasks (intents = bits attributs, extents = bits objets).
- **Étapes** :
  - `prime_attrs(X)` : `extent = all_objs` puis AND successifs sur les colonnes des attributs présents dans `X`.
  - `prime_objs(Y)` : `intent = all_attrs` puis AND successifs sur les lignes des objets présents dans `Y`.
  - `closure(X)` : `extent = X'` puis `intent = (X')'`.
- **Interactions** : `closure()` est appelée à chaque pas de `next_closure()`.

### Bloc : `next_closure(current_intent, ...)`

- **Rôle** : produire l’intent fermé suivant en **ordre lectique** (NextClosure).
- **Données** : `current_intent` (bitmask), paramètres de contexte.
- **Pseudo-étapes** :
  1. pour `i` de `|M|-1` à `0` :
     - si `i` n’est pas dans l’intent courant : former `candidate` (préfixe < i + i)
     - fermer `candidate` → `d_intent`
     - test canonique : préfixe de `d_intent` == préfixe de `current_intent`
     - si ok : retourner `(d_intent, d_extent)`
  2. sinon retourner `None` (fin).
- **Interactions** : piloté par `next_closure_partition()`.

### Bloc : `compute_adaptive_batch_size()` / `get_available_memory_mb()`

- **Rôle** : adapter `batch_size` à la RAM disponible.
- **Approche** :
  - lit `MemAvailable` sous Linux, réserve `MEMORY_RESERVE_MB`.
  - prend ~40% du reste pour buffer.
  - estime un coût par concept (`bytes_per_concept`) et déduit un batch.
- **Point notable** : heuristique (pas une mesure exacte) mais utile pour garder le buffer borné.

### Bloc : `next_closure_partition(...)`

- **Rôle** : énumérer tous les concepts et **flusher sur disque** périodiquement.
- **Données** :
  - `buffer: list[(intent_mask, extent_mask)]`
  - `partition_dir/partK/chunkX.json`
- **Étapes** :
  1. nettoyer/créer `partition_dir`
  2. initialiser avec `closure(∅)`
  3. boucle NextClosure : append au buffer, afficher progression, flush si plein
  4. flush du reste, `gc.collect()`.
- **Interactions** : écrit via `save_partition()`.

### Bloc : `save_partition(...)`

- **Rôle** : sérialiser un lot de concepts en JSON, découpé en **chunks**.
- **Données** : conversion `bitmask -> list[str]` pour intent/extent.
- **Étapes** :
  1. pour chaque chunk (taille `CHUNK_SIZE`) : construire `records`
  2. `json.dump(records)` dans `chunkK.json`
  3. `del records`.
- **Trade-off** : JSON est lisible mais volumineux ; la compacité est sacrifiée pour la simplicité.

### Bloc : `load_partitions(...)`

- **Rôle** : relire partitions + chunks, reconstruire bitmasks, dédupliquer, trier.
- **Données** :
  - `seen: set[(intent_mask, extent_mask)]` (filet de sécurité)
  - `concepts: list[(intent_mask, extent_mask)]`
- **Étapes** :
  1. lister `part*` puis `chunk*.json` dans l’ordre numérique
  2. charger un chunk, convertir intent/extent en bitmask
  3. dédupliquer via `seen`
  4. `del raw_data; gc.collect()`
  5. trier `concepts` par `(popcount(intent), intent)`.

### Bloc : `compute_edges(concepts)`

- **Rôle** : calculer la **relation de couverture** (Hasse) : arêtes `child -> parent`.
- **Données** :
  - `intent_cards: list[int]` = |intent|
  - `level_index[k]` = indices des concepts de cardinalité k
  - `accepted_parents: list[int]` stocke les intents des parents acceptés
- **Étapes** :
  1. construire `intent_cards`, `level_index`
  2. pour chaque concept `c` :
     - parcourir les niveaux `k-1..0`
     - tester `d_intent ⊂ c_intent`
     - rejeter si dominé par un parent déjà accepté (`d ⊂ p`)
     - sinon accepter : `edges.append((c, d))`.
- **Interaction** : `write_dot()` utilise ces arêtes pour dériver parents/enfants.

### Bloc : `compute_own_labels()` + `write_dot()`

- **Rôle** : produire des labels **réduits** (sans répétition d’héritage) + écrire DOT.
- **Principe** :
  - attributs propres d’un concept = intent(c) − union intents(parents)
  - objets propres d’un concept = extent(c) − union extents(enfants)
- **DOT** :
  - nœuds triés/numérotés par l’ordre de `concepts`
  - couleur selon le nombre d’objets propres (0 → lightblue, 1 → aucune, >1 → orange)
  - arêtes triées.

## 4) Algorithmes utilisés

### 4.1 NextClosure (Ganter) — énumération lectique des intents fermés

- **Où** : `next_closure()` + bouclage dans `next_closure_partition()`.
- **Pourquoi** : c’est l’algorithme standard pour énumérer tous les ensembles fermés $X=X''$ de manière déterministe, sans doublons.
- **Extrait clé** :

```python
prefix_mask = (1 << i) - 1
candidate = (current_intent & prefix_mask) | bit_i
(d_intent, d_extent) = closure(candidate, ...)
if (d_intent & prefix_mask) == (current_intent & prefix_mask):
    return d_intent, d_extent
```

- **Complexité (justifiable par le code)** : à chaque pas, jusqu’à `|M|` closures, chaque closure fait des AND sur des bitmasks d’objets + d’attributs ⇒ $O(|M|\times (|G|+|M|)/w)$ par concept, donc $O(|L|\times |M|\times (|G|+|M|)/w)$ au total.
- **Limites / hypothèses** : explosion combinatoire possible : $|L|$ peut être exponentiel (pire cas). Le code assume que le contexte (matrice bitmask) tient en RAM.

### 4.2 Fermeture FCA $X''$ via double prime

- **Où** : `closure()`, `prime_attrs()`, `prime_objs()`.
- **Pourquoi** : propriété fondamentale de FCA : (extent,intent) d’un concept vérifient $A=B'$ et $B=A'$.
- **Complexité** : $O(|G|+|M|)$ ANDs au niveau bitset (donc $O((|G|+|M|)/w)$ en coût bit).

### 4.3 Couverture (Hasse) par filtrage “maximal sous-ensemble” + index de niveaux

- **Où** : `compute_edges()`.
- **Description** : pour chaque concept `c`, recherche de parents `d` tels que `intent(d) ⊂ intent(c)` et maximalité assurée par une élimination des candidats dominés (`d ⊂ p`). L’index `level_index` réduit l’espace de comparaison.
- **Pourquoi** : construire le Hasse diagram nécessite d’enlever les arêtes transitives (ne garder que les couvertures).
- **Complexité** : pire cas proche de $O(|L|^2)$ tests de sous-ensemble, mais pratique améliorée par séparation par niveaux.
- **Limites** : si `|L|` est très grand (centaines de milliers / millions), même cette approche devient coûteuse (temps) et la sortie DOT devient volumineuse.

### 4.4 Partitionnement “sur flux de sortie” + chunking JSON

- **Où** : `next_closure_partition()` + `save_partition()`.
- **Pourquoi** : contrôler le pic mémoire lors de l’énumération : on ne conserve pas tous les concepts en RAM pendant l’énumération.
- **Limite** : la phase finale (`load_partitions` + `compute_edges`) recharge tout en RAM ; l’économie mémoire porte surtout sur la phase d’énumération.

## 5) Analyse technique

### Structures de données

- **Bitmasks (int)** :
  - `obj_attrs[g]` encode une ligne ; `attr_objs[m]` encode une colonne.
  - Avantages : compact, AND rapide, subset test via `(a & b) == a`.
  - Alternatives : `array('Q')`/`bitarray`/`numpy` pour un contrôle mémoire plus fin (non utilisé ici).
- **Partitions sur disque** : répertoires + JSON chunks.
  - Avantages : simple, inspectable.
  - Inconvénient : volumineux, conversion bitmask↔noms coûteuse.
- **Index par niveaux** : `level_index` dans `compute_edges()`.
  - Réduit les comparaisons inutiles entre niveaux.

### Choix d’implémentation / invariants

- Invariant central : tous les `intent_mask` produits par NextClosure sont **fermés** (`X=X''`) et cohérents avec leur `extent` issu de la fermeture.
- Déterminisme :
  - ordre des partitions : séquentiel
  - tri final : `(popcount(intent), intent)`
  - tri des arêtes dans `write_dot()`.

### Points subtils

- `get_available_memory_mb()` : dépendance Linux ; fallback à 1024 Mo si `/proc/meminfo` indisponible.
- `compute_adaptive_batch_size()` : estimation “bytes_per_concept” heuristique ; elle ne tient pas compte précisément de la taille binaire des `int` (qui dépend du nombre de bits réellement utilisés).
- `load_partitions()` : le `seen-set` peut devenir très gros si énormément de concepts (double stockage temporaire : `concepts` + `seen`). C’est un garde-fou, mais en très grand cela peut devenir le vrai pic mémoire.
- `compute_edges()` stocke `accepted_parents` comme une liste d’intents (entiers) et non d’indices : c’est suffisant pour le test `d ⊂ p`, mais ça empêche toute réutilisation d’informations (pas de caching des relations) — choix de simplicité.

### Performance (hotspots probables)

- **Énumération** : coût dominé par `closure()` appelée très souvent (NextClosure fait jusqu’à `|M|` closures par concept).
- **Conversion JSON** : `bitmask_to_names` sur intent/extent fait une boucle sur tous les attributs/objets pour chaque concept → peut coûter cher si beaucoup de concepts.
- **Arêtes** : `compute_edges()` peut être quadratique en `|L|`.

### Robustesse (validation, exceptions)

- Validation minimale : présence du fichier CSV, affichage usage.
- Hypothèses non vérifiées explicitement :
  - format exact du CSV (valeurs seulement 0/1), cohérence du nombre de colonnes.
  - unicité des noms d’objets/attributs (sinon `name_to_idx` écrase silencieusement).
- Résilience mémoire :
  - libération explicite (`del`, `gc.collect`) dans les étapes de chargement/écriture.
  - vérification RAM avant chargement d’un chunk.

## 6) Qualité du code

### Grille d’évaluation

- **Lisibilité** : bonne.
  - Gros docstring, sections commentées “Étape 1..10”, noms explicites.
  - Quelques fonctions longues mais structurées.
- **Modularité** : correcte.
  - Pipeline clair, fonctions séparées par responsabilité.
  - Une seule unité de compilation (fichier unique) : simple mais moins réutilisable.
- **Maintenabilité** : bonne à moyenne.
  - Beaucoup de documentation interne.
  - Quelques heuristiques (batch adaptatif) non testées formellement.
- **Testabilité** : moyenne.
  - Fonctions pures (closure/next_closure) testables.
  - Beaucoup d’I/O dans `next_closure_partition`/`load_partitions` : tests nécessitent fichiers temporaires.
- **Bonnes pratiques Python** : correct.
  - Utilisation de `with open`, exceptions gérées pour `/proc/meminfo`, suppression de répertoires via `shutil.rmtree`.
  - Pas de typing hints : acceptable, mais pour du “senior” on pourrait en vouloir (constat, pas une demande de changement).

### ✅ Points forts

- Implémentation standard et déterministe de NextClosure.
- Contrôle mémoire pendant l’énumération via flush disque + `gc.collect()`.
- Index par niveaux pour limiter le coût du calcul des arêtes.
- Sortie DOT stable (tri concepts/arêtes) et labels réduits (évite la verbosité).

### ⚠️ Points à améliorer

- Phase finale charge **tous** les concepts en RAM (et un `seen-set`) : le partitionnement n’élimine pas le pic mémoire global si `|L|` est gigantesque.
- Format JSON verbeux : taille disque et coût CPU (conversion noms) potentiellement élevés.
- Validation d’entrée minimaliste (doublons de noms, colonnes manquantes, valeurs non binaires).
- `compute_edges()` reste potentiellement $O(|L|^2)$.

### 🔧 Recommandations prioritaires (max 5)

1. **Documenter explicitement la limite** : l’étape `compute_edges()` suppose `concepts` en RAM ; au-delà, le DOT sera de toute façon très gros.
2. Ajouter une **validation légère** du CSV (valeurs {0,1}, cohérence colonnes) et un contrôle d’unicité des noms.
3. Envisager un format de partition plus compact (ex. bitmasks sérialisés) si le volume JSON devient un problème.
4. Mesurer (profiling) les hotspots sur gros contextes : `closure()` et `bitmask_to_names`.
5. Clarifier la stratégie mémoire : `seen` peut être optionnel si on fait confiance à NextClosure (mais garde-fou utile).

## 7) Résumé des points clés

- Le script calcule un treillis FCA complet : CSV → concepts → arêtes (Hasse) → DOT.
- Le contexte est représenté en bitmasks (`obj_attrs`, `attr_objs`), ce qui rend `closure()` efficace via AND.
- L’énumération repose sur NextClosure (ordre lectique + test de canonicité), déterministe et sans doublons.
- La consommation mémoire pendant l’énumération est bornée par un buffer `batch_size` adaptatif, vidé sur disque en partitions/chunks JSON.
- Les partitions sont ensuite relues, dédupliquées, triées pour numéroter les nœuds de manière stable.
- Les arêtes de couverture sont calculées via un index par niveaux (`|intent|`) et un filtrage des candidats dominés.
- Les labels DOT sont réduits : seuls attributs/objets “propres” sont affichés, pour éviter la répétition.
- Limite structurelle : la phase finale (fusion + arêtes) requiert une liste globale des concepts en mémoire et peut devenir $O(|L|^2)$.
- Robustesse : validation d’entrée minimale ; hypothèses sur CSV et unicité des noms.
- Code bien documenté et maintenable, avec trade-offs assumés (simplicité vs compacité disque/CPU).
