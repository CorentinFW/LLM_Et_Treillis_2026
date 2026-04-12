# 1. Hypotheses et perimetre
- **Hypotheses minimales** :
  - Le contexte formel est strictement binaire (`0`/`1`). Toute autre valeur entraîne un rejet.
  - La première colonne représente l'identifiant d'objet (string). Les colonnes suivantes sont des attributs.
  - Le treillis généré est un poset fini borné (existe toujours un top et un bottom, même si dégénéré).
  - La RAM disponible est strictement inférieure à la taille nécessaire pour stocker le treillis complet en mémoire vive.
- **Cas limites explicites** :
  - Contexte vide (0 objet ou 0 attribut) → treillis à 1 nœud (top=bottom) ou fichier invalide détecté.
  - Contexte plein/trous (`1` partout ou `0` partout) → treillis de type chaîne ou anti-chaîne.
  - Fichiers `.dot` de 0 octet → état d'échec explicite, déclenche régénération ou abort.
  - Extents massifs (single-node) → gérés par écriture différée, pas de concaténation en mémoire.
- **Compromis performance vs mémoire** : Privilégier le streaming disque, les fusions externes K-way, et le calcul par blocs plutôt que la cache totale en RAM. Sacrifier la vitesse d'énumération pure pour garantir la terminaison sans OOM (Out-Of-Memory). Déterminisme absolu requis sur les identifiants et l'ordre des arêtes.

# 2. Contrat Input/Output derive de la documentation
**Contrat d'entrée (CSV) :**
- **Obligatoire** : En-tête valide (première cellule vide ou `""`), séparateur unique par fichier (`;` ou `,`), nombre de colonnes constant, données binaires (`0`/`1`) à partir de la colonne 2.
- **Optionnel** : Guillemets autour des champs, identifiants textuels ou numériques en colonne 1.
- **Invalide** : Largeur variable, valeurs hors `{0,1}`, fichier tronqué, séparateur mixte.
- **Validation** : Détection auto du séparateur (scan première ligne), vérification binaire stricte, vérification de la largeur ligne par ligne (ou par échantillon représentatif + checksum taille).

**Contrat de sortie (DOT) :**
- **Obligatoire** : Enveloppe `digraph G { \n rankdir=BT; \n ... \n }`. Nœuds nommés par entiers consécutifs. Format label `{<id> (I: <x>, E: <y>)|<intent>|<extent>}`. Arêtes `u -> v;`.
- **Optionnel** : Attributs de couleur `fillcolor` selon règle stricte.
- **Invalide** : Fichier 0 octet, syntaxe Graphviz brisée, nœuds sans label, cycles, couleurs hors spec, identifiants non contigus.
- **Stabilité** : Tri topologique ou lexical des nœuds, tri des arêtes par `(src, dst)`. Hash stable du fichier final pour un même input.

# 3. Modele conceptuel FCA et invariants
- **Définitions formelles** :
  - Contexte : $K = (G, M, I)$ avec $G$ (objets), $M$ (attributs), $I \subseteq G \times M$ (incidence).
  - Opérateurs de dérivation : $A' = \{m \in M \mid \forall g \in A, (g,m) \in I\}$ et $B' = \{g \in G \mid \forall m \in B, (g,m) \in I\}$.
  - Concept : $(A,B)$ tel que $A' = B$ et $B' = A$. $A$ = extent, $B$ = intent.
  - Fermeture : $X \mapsto X''$. Tout concept vérifie $B = B''$.
- **Ordre partiel & couverture** :
  - $(A_1,B_1) \le (A_2,B_2) \iff A_1 \subseteq A_2 \iff B_1 \supseteq B_2$.
  - Couverture $C_1 \prec C_2$ si $C_1 < C_2$ et $\nexists C_3 : C_1 < C_3 < C_2$.
- **Invariants de correction** :
  1. Fermeture stricte sur tout intent/extent généré.
  2. Préservation des nœuds intermédiaires (aucun saut de rang non justifié par l'absence d'intermédiaire).
  3. Cardinalités cohérentes : `x` dans label = $|B|$, `y` = $|A|$.
  4. Graphe acyclique, connexe, borné (top et bottom présents).

# 4. Architecture logique proposee
- **Orchestrateur** : Pilote séquentiel sans parallélisme implicite pour garantir le déterminisme et maîtriser la RAM.
- **Modules** :
  1. `InputValidator` : Parse CSV, détecte séparateur, valide binaire, émet métadonnées.
  2. `DecompositionEngine` : Scinde le contexte en blocs d'attributs, génère sous-treillis.
  3. `ConceptSpiller` : Écrit les concepts générés vers le disque (fichiers plats indexés).
  4. `ExternalMerger` : Fusion K-way des fichiers de concepts, déduplique, assigne IDs stables.
  5. `CoverRelationCalculator` : Calcule les arêtes de couverture par blocs, persiste la liste d'arêtes.
  6. `DOTRenderer` : Lit nœuds + arêtes depuis disque, applique formatage, écrit DOT en streaming.
- **Flux de données** : `CSV → [Validation] → [Partition] → [Énumération blocs → Flush] → [Merge/Dedup] → [Calcul Couverture] → [Stream DOT]`
- **Gestion des erreurs** : Si un chunk corrompu est détecté à la lecture, il est marqué invalide, nettoyé, et régénéré depuis la source binaire.

# 5. Structures de donnees
- **En mémoire (limité)** :
  - `BlockContext` : Sous-matrice (indices objets, indices attributs).
  - `ConceptRecord` : `{id: int|None, intent_hash: int, intent_sorted: tuple, extent_count: int, extent_disk_ref: int}`.
  - `EdgeBatch` : `(src_id, dst_id)` bufferisé avant flush disque.
- **Sur disque (persistance)** :
  - `chunks/concept_chunk_N.bin` : Fichiers triés par `intent_sorted`. Format compact : longueur intent + valeurs attributs + hash extent + offset fichier extent + count extent.
  - `extents_db/` : Stockage des extents complets (optionnellement compressés). Référence par offset.
  - `edges.csv` : Liste triée des arêtes `(u, v)`.
  - `lattice_index.btree` : Index clé=valeur sur `intent_sorted → node_metadata` pour recherche rapide sans tout charger.

# 6. Strategie de decomposition memoire
- **Partitionnement** : Découpage des attributs $M$ en $k$ sous-ensembles $M_i$ de taille fixe (ex: 8-16 attributs). Taille $k$ ajustée pour que le treillis local tienne dans une fraction définie de la RAM cible (ex: 20%).
- **Génération par bloc** : Pour chaque $M_i$, extraction du contexte restreint $K_i = (G, M_i, I|_{M_i})$. Énumération des concepts via NextClosure adaptée. Chaque concept est projeté sur le contexte complet pour recalculer $intent''$ et $extent''$.
- **Évacuation** : Dès que le buffer de concepts atteint un seuil critique, écriture immédiate sur disque sous forme triée. Nettoyage explicite de la RAM (garbage collector forcé, libération références). Seul le `lattice_index` (méta-données légères) est conservé en cache.
- **Robustesse** : Chaque fichier chunk inclut un header avec checksum CRC32. À la lecture, vérification stricte. Échec → régénération du chunk $i$ seul.

# 7. Strategie de fusion et deduplication
- **Fusion externe** : Merge K-way classique sur les fichiers `chunks/concept_chunk_*.bin`. Pointeurs maintenus sur un seul concept par fichier en RAM. Sélection du plus petit selon l'ordre lexical des intents.
- **Clé canonique** : Tuple trié des indices d'attributs appartenant à l'intent ferme. Cette clé est invariante et garantit l'unicité sémantique du concept.
- **Déduplication** : Si deux concepts en flux partagent la même clé canonique, leurs extents sont unis et recalculés ($B' \to$ nouvel extent $\to$ $A'' \to$ nouvel intent). Le résultat est écrit une seule fois. Les doublons sont ignorés après fusion.
- **Garantie déterministe** : L'ordre lexical des intents est strict. L'affectation des IDs de nœuds est séquentielle ($0$ à $N-1$) après fusion totale. Aucun saut, aucun hash aléatoire. Relecture identique du contexte → DOT identique (à l'exception des timestamps absents).

# 8. Strategie optimisee des relations de couverture
- **Évitement du $O(N^2)$** : Pas de comparaison exhaustive. Utilisation de la propriété FCA : $C_1 \prec C_2 \iff \exists m \in M \setminus intent(C_1)$ tel que $(intent(C_1) \cup \{m\})'' = intent(C_2)$ et $|intent(C_2)| = |intent(C_1)| + 1$ (ou différence minimale d'extent dans les treillis non gradués).
- **Indexation par taille** : Chargement par tranches triées par $|intent|$ croissante. Pour chaque concept $C$, on teste l'ajout d'un seul attribut manquant $m$, calcul de la fermeture, et lookup dans l'index disque. Si trouvé $\to$ arête valide.
- **Traitement par blocs** : Les arêtes sont écrites dans `edges.csv` dès qu'elles sont découvertes. Aucune structure de graphe complète n'est instanciée en RAM.
- **Détection d'absence d'intermédiaire** : Si $(intent(C) \cup \{m\})''$ existe dans l'index et qu'aucun concept intermédiaire n'a été trouvé pour cet ajout, la relation est une couverture directe. Les arêtes redondantes (transitives) sont filtrées par construction.

# 9. Specification DOT (labels, couleurs, tri, stabilite)
- **Numerotation** : IDs entiers contigus $0 \dots N-1$, attribués dans l'ordre de fusion (lexical intent). Stabilité garantie.
- **Construction labels** : Format `{<id> (I: <x>, E: <y>)|<intent>|<extent>}`. 
  - `<intent>` et `<extent>` : listes triées lexicographiquement des attributs/objets.
  - Séparateur interne : virgule + espace. Pas de guillemets superflus.
  - Compactage : Si la longueur totale dépasse un seuil de sécurité (ex: 2048 chars), troncature avec suffixe `...` uniquement pour les nœuds single-node massifs, tout en conservant l'information `(I: x, E: y)` intacte.
- **Logique couleurs** (stricte) :
  - `|A| == 0` → `fillcolor="lightblue";`
  - `|A| == 1` → aucune directive `fillcolor` (transparent par défaut).
  - `|A| > 1` → `fillcolor="orange";`
- **Tri final** : Nœuds écrits par ID croissant. Arêtes écrites en double tri `(src ASC, dst ASC)`. Fermeture `}` sur nouvelle ligne.

# 10. Pseudo-code des composants critiques

```text
FONCTION ParseAndValidate(csv_path):
  DETECT séparateur (première ligne, compte ';' vs ',')
  OUVRIR flux CSV avec détection guillemets
  LIRE en-tête → vérifier cellule[0] vide/""
  INITIALISER liste_objets, liste_attributs, compteur_ligne
  POUR CHAQUE ligne restante:
    SI longueur(ligne) != longueur(en-tête) → LEVER_ERREUR("Largeur variable")
    POUR cellule de 1 à fin:
      SI cellule NOT IN {"0", "1"} → LEVER_ERREUR("Valeur non binaire")
    AJOUTER objet_id et vecteur binaire (mmap/référence lazy)
  RETOURNER contexte_valide, métadonnées

FONCTION EnumerateAndSpill(block_attrs, disk_path):
  INITIALISER contexte_partiel K_i
  INITIALISER générateur NextClosure sur K_i
  POUR CHAQUE concept généré (A_i, B_i):
    calculer fermeture complète sur contexte total → (A, B)
    calculer hash_canonique = hash(sorted(B))
    écrire dans fichier trié temporaire (B, |A|, référence_A, hash_canonique)
    SI mémoire > SEUIL → FLUSH fichier, libérer buffer
  FERMER, TRIER fichier par clé canonique, vérifier checksum

FONCTION MergeDeduplicateAndAssignIDs(chunk_files, global_index_path):
  INITIALISER file_readers[K] sur les fichiers triés
  INITIALISER heap_priorité par clé canonique
  node_id ← 0
  TANT QUE heap non vide:
    RETIRER plus petite clé → record
    SI clé == clé_précédente:
      UNION extent courant avec extent précédent
      recalculer fermeture
      remplacer précédent dans sortie
    SINON:
      ASSIGNER node_id au record
      ÉCRIRE dans global_index_path (node_id, metadata)
      node_id ← node_id + 1
      clé_précédente ← clé
  RETOURNER nombre_noeuds

FONCTION ComputeCoverRelationsOptimized(global_index, edge_output):
  OUVRIR index par blocs de taille N (triés par |intent|)
  POUR CHAQUE concept C dans bloc:
    POUR CHAQUE attribut m ∉ intent(C):
      calculer fermeture intent_candidate = (intent(C) ∪ {m})''
      RECHERCHER intent_candidate dans global_index (lookup binaire)
      SI trouvé D:
        VÉRIFIER qu'aucun intermédiaire E n'existe entre C et D
        (contrôle par différence de taille et lookup index)
        SI validation OK → ÉCRIRE (C.id, D.id) dans edge_output
  FERMER flux

FONCTION RenderDOT(node_index, edge_list, dot_path):
  OUVRIR dot_path en écriture streaming
  ÉCRIRE "digraph G { \n rankdir=BT;\n"
  POUR node_id DE 0 À N-1:
    LIRE métadonnées node_id
    CONSTRUIRE label = format_label(node_id, intent, extent)
    APPLIQUER couleur SELON |extent| (règle lightblue/none/orange)
    ÉCRIRE ligne nœud
  POUR (src, dst) DANS edge_list (déjà trié):
    ÉCRIRE "src -> dst;"
  ÉCRIRE "}"
  FERMER
```

# 11. Plan de verification et criteres d'acceptation
- **Tests unitaires** :
  - Contexte minimal (1x1, 2x2) → 1 à 4 nœuds.
  - Contexte dégénéré (tous `1`) → chaîne linéaire.
  - Contexte vide/trou → top/bottom coïncidents.
  - Contexte stress (déclenche décomposition) → vérification absence OOM.
- **Validation structurelle DOT** :
  - Syntaxe Graphviz valide (analyseur `graphviz` ou regex stricte).
  - Comptage : `nb_noeuds` = `nb_concepts_énumérés`, `nb_arêtes` correspond au calcul de couverture.
  - Acyclicité : parcours DFS confirme DAG.
  - Connectivité : graphe connexe, top/bottom atteignables.
- **Non-regression & Robustesse** :
  - Hash SHA-256 du `.dot` identique sur 3 exécutions consécutives (déterminisme).
  - Labels compacts : aucun dépassement de taille sauf cas massifs explicitement tronqués.
  - Injection de corruption sur un chunk → détection checksum, régénération automatique, succès final.
  - Comparaison avec sortie FCA4J de référence sur `Animals11.csv` : isomorphisme structurel strict.

# 12. Checklist pre-implementation
- [ ] Environnement configuré (Python 3.x, bibliothèque standard suffisante, espace disque > 2x taille contextes).
- [ ] Spécification du format binaire des chunks validée (offsets, CRC, alignement).
- [ ] Algorithme NextClosure implémenté en version "lazy" et testé sur sous-contextes.
- [ ] Index disque (`lattice_index`) conçu pour recherche binaire rapide sans chargement total.
- [ ] Logique de calcul de couverture par blocs validée sur treillis théoriques connus.
- [ ] Template DOT et moteur de rendu streaming verrouillés (conformité `rankdir=BT`, record shape, règle couleurs).
- [ ] Stratégie de fallback/chunk regeneration documentée et simulée.
- [ ] Jeu de tests multi-échelle prêt (petit, moyen, large, dégénéré, corrompu).
- [ ] Validation des hypothèses d'entrée/sortie validée contre `Documentation/Modele_InputEtOutput.md`.
- [ ] Architecture approuvée pour absence totale de code de suivi temporel et garantie de non-rétention du treillis en RAM.