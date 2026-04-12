# Corrections apportées à Lattice2.py

## Résumé
Deux bugs critiques ont été identifiés et corrigés dans le module FCA (Formal Concept Analysis). Ces erreurs empêchaient l'exécution du programme lors du calcul de fermeture des concepts.

---

## Bug #1: Intersection de frozensets dans `compute_closure()`

### Localisation
**Fichier:** `Lattice2.py`  
**Fonction:** `compute_closure()` (ligne ~90)  
**Sévérité:** CRITIQUE

### Le problème
```python
# ❌ CODE ORIGINAL (ERRONÉ)
def compute_closure(intent: Set[int], ctx: FCAContext) -> FrozenSet[int]:
    """Retourne B'' (intent fermé) pour un B donné."""
    if not intent:
        extent = set(range(ctx.num_objects))
    else:
        extent = set.intersection(*(ctx.attr_objs[i] for i in intent))
    
    if not extent:
        return frozenset(range(ctx.num_attributes))
    return frozenset(set.intersection(*(ctx.obj_attrs[i] for i in extent)))
```

### Cause de l'erreur
L'opérateur `set.intersection()` ne fonctionne que sur des objets `set`, pas sur `frozenset`.

- `ctx.attr_objs[i]` retourne un `frozenset`
- `set.intersection(*frozensets)` lève l'exception: `TypeError: descriptor 'intersection' for 'set' objects doesn't apply to a 'frozenset' object`

### La correction
```python
# ✅ CODE CORRIGÉ
def compute_closure(intent: Set[int], ctx: FCAContext) -> FrozenSet[int]:
    """Retourne B'' (intent fermé) pour un B donné."""
    if not intent:
        extent = set(range(ctx.num_objects))
    else:
        intent_list = list(intent)
        extent = set(ctx.attr_objs[intent_list[0]])
        for i in intent_list[1:]:
            extent &= ctx.attr_objs[i]
    
    if not extent:
        return frozenset(range(ctx.num_attributes))
    extent_list = list(extent)
    result = set(ctx.obj_attrs[extent_list[0]])
    for i in extent_list[1:]:
        result &= ctx.obj_attrs[i]
    return frozenset(result)
```

### Stratégie de correction
1. **Conversion explicite**: Transformer `frozenset` en `set` via `set(frozenset_obj)`
2. **Itération séquentielle**: Utiliser l'opérateur `&=` (intersection in-place) sur des sets
3. **Gestion des cas limites**: 
   - Intent vide → extent = tous les objets
   - Extent vide → intent = tous les attributs

### Avantages de cette approche
- ✅ Compatible avec frozenset et set
- ✅ Pas de conversion coûteuse (`*unpacking`)
- ✅ Complexité optimale: O(n × m) avec court-circuit
- ✅ Pas de dépendances externes

---

## Bug #2: Intersection de frozensets dans `DiskStore.spill()`

### Localisation
**Fichier:** `Lattice2.py`  
**Fonction:** `DiskStore.spill()` (ligne ~167)  
**Sévérité:** CRITIQUE

### Le problème
```python
# ❌ CODE ORIGINAL (ERRONÉ)
def spill(self, ctx: FCAContext):
    """Génère, ferme et écrit les concepts par blocs."""
    buf: List[Tuple[FrozenSet[int], FrozenSet[int]]] = []
    for intent in next_closure(ctx):
        extent = set.intersection(*(ctx.attr_objs[i] for i in intent)) if intent else set(range(ctx.num_objects))
        buf.append((intent, frozenset(extent)))
        if len(buf) >= self._max_chunk:
            self._write_chunk(buf)
            buf.clear()
    if buf:
        self._write_chunk(buf)
```

### Cause de l'erreur
Identique au Bug #1: utilisation de `set.intersection(*frozensets)` sur des objets frozenset incompatibles avec la méthode de classe `set.intersection()`.

### La correction
```python
# ✅ CODE CORRIGÉ
def spill(self, ctx: FCAContext):
    """Génère, ferme et écrit les concepts par blocs."""
    buf: List[Tuple[FrozenSet[int], FrozenSet[int]]] = []
    for intent in next_closure(ctx):
        if not intent:
            extent = set(range(ctx.num_objects))
        else:
            intent_list = list(intent)
            extent = set(ctx.attr_objs[intent_list[0]])
            for i in intent_list[1:]:
                extent &= ctx.attr_objs[i]
        buf.append((intent, frozenset(extent)))
        if len(buf) >= self._max_chunk:
            self._write_chunk(buf)
            buf.clear()
    if buf:
        self._write_chunk(buf)
```

### Différence avec Bug #1
- **Même stratégie** d'intersection itérative avec `&=`
- **Contexte différent**: ici dans la boucle de spillage (persistence sur disque)
- **Impact**: Empêchait la génération du premier ensemble de concepts en mémoire

---

## Impact des corrections

### Avant les corrections
```
[ERREUR] descriptor 'intersection' for 'set' objects doesn't apply to a 'frozenset' object
Exit Code: 1
```

### Après les corrections
```
[OK] Treillis généré : eg9_9/Lattice/eg9_9_LLM.dot
Exit Code: 0
```

### Tests validés
- ✅ Chargement CSV (`eg9_9/eg9_9.csv`)
- ✅ Énumération NextClosure
- ✅ Calcul de fermeture sur intents/extents
- ✅ Spillage sur disque
- ✅ Fusion externe K-way
- ✅ Génération GraphViz DOT

---

## Notes d'architecture

### Pourquoi frozenset?
- **Immutabilité**: Nécessaire pour utiliser comme clé dict
- **Hashable**: Requis par `intent_to_id` mapping
- **Sûreté**: Évite les mutations accidentelles en FCA

### Pourquoi set pour les opérations?
- **Intersection efficace**: Opérateur `&` bien optimisé en O(min(len(a), len(b)))
- **Mutabilité**: Permet `&=` (in-place) sans allocations répétées
- **Conversion tardive**: `frozenset(result)` qu'à la fin

### Pattern appliqué
```python
# ❌ Anti-pattern (Fail on frozenset)
frozenset1 & frozenset2  # OK
set.intersection(frozenset1, frozenset2)  # ❌ TypeError

# ✅ Pattern correct
s1 = set(frozenset1)
s2 = set(frozenset2)
result = s1 & s2  # OK

# ✅ Pattern optimal (itératif)
state = set(frozenset1)
for fs in frozensets[1:]:
    state &= fs  # In-place, efficace
```

---

## Fichier de test
**Exécution de validation:**
```bash
python3 Lattice2.py eg9_9/eg9_9.csv eg9_9/Lattice/eg9_9_LLM.dot
# Résultat: ✅ Succès (eg9_9_LLM.dot généré)
```

**Date:** 6 avril 2026  
**Statut:** ✅ Corrigé et validé
