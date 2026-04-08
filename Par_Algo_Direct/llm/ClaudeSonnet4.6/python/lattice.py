# =============================================================================
# Fichier      : lattice_builder.py
# Objectif     : Construction d'un treillis de Galois (Analyse Formelle de
#                Concepts) à partir d'un fichier CSV binaire, et génération
#                d'un fichier DOT (Graphviz) représentant le diagramme de Hasse.
# Bibliothèque : AUCUNE dépendance externe — uniquement la bibliothèque
#                standard Python (csv, sys, time).
# Algorithme   : Next Closure de Bernhard Ganter (construction en une passe
#                globale sur le contexte formel complet).
# Installation : aucune — fonctionne avec Python 3.8+ natif.
# Exemple      : python lattice_builder.py Animals11.csv Animals11_out.dot
# =============================================================================

import sys
import time
import csv


# =============================================================================
# 1. LECTURE DU FICHIER CSV
#    Format : séparateur ";", première colonne = noms des objets,
#    colonnes suivantes = attributs binaires (0 ou 1), ligne d'en-tête.
# =============================================================================
def load_csv(path):
    """
    Lit le fichier CSV et retourne :
      - obj_names  : liste des noms d'objets (str)
      - attr_names : liste des noms d'attributs (str)
      - table      : liste de frozenset, table[i] = indices des attributs
                     possédés par l'objet i
    """
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader)
        attr_names = header[1:]  # ignore la 1ère colonne (noms d'objets)

        obj_names = []
        table = []
        for row in reader:
            if not row:
                continue
            obj_names.append(row[0])
            owned = frozenset(
                j for j, v in enumerate(row[1:]) if v.strip() == '1'
            )
            table.append(owned)

    return obj_names, attr_names, table


# =============================================================================
# 2. OPÉRATEURS DE GALOIS
#    prime_obj(A) : ensemble d'objets  → attributs communs à tous ces objets
#    prime_att(B) : ensemble d'attributs → objets possédant tous ces attributs
#    Ces deux opérateurs forment la connexion de Galois fondamentale de l'AFC.
# =============================================================================
def make_galois(n_obj, n_att, table):
    """Retourne les deux opérateurs de la connexion de Galois."""
    all_objects = frozenset(range(n_obj))
    all_attrs   = frozenset(range(n_att))

    def prime_obj(obj_set):
        """Attributs communs à tous les objets de obj_set."""
        if not obj_set:
            return all_attrs
        result = all_attrs
        for g in obj_set:
            result = result & table[g]
        return result

    def prime_att(att_set):
        """Objets possédant tous les attributs de att_set."""
        if not att_set:
            return all_objects
        result = all_objects
        for m in att_set:
            col = frozenset(g for g in range(n_obj) if m in table[g])
            result = result & col
        return result

    return prime_obj, prime_att


# =============================================================================
# 3. ALGORITHME NEXT CLOSURE (Ganter, 1999)
#    Génère TOUS les ensembles fermés (intensions des concepts) en une seule
#    passe lexicographique sur l'ensemble des attributs, sans boucle externe
#    objet par objet. C'est l'algorithme de référence pour l'AFC.
# =============================================================================
def next_closure(current, n_att, prime_att, prime_obj):
    """
    Calcule l'ensemble fermé lexicographiquement suivant après `current`.
    Retourne None si `current` est le dernier ensemble fermé (= tous les attrs).
    """
    for i in range(n_att - 1, -1, -1):
        if i in current:
            current = current - {i}
        else:
            candidate = current | {i}
            closure = prime_obj(prime_att(candidate))
            # Condition lexicographique : tous les j < i dans closure
            # doivent déjà être dans current
            if all(j in current for j in closure if j < i):
                return closure
    return None


def build_concepts(n_obj, n_att, table):
    """
    Construit la liste complète des concepts formels via Next Closure.
    Chaque concept est un tuple (intent: frozenset, extent: frozenset).
    La construction s'effectue en une seule passe globale sur le contexte.
    """
    prime_obj, prime_att = make_galois(n_obj, n_att, table)

    concepts = []
    # Départ : fermeture de l'ensemble vide = attributs communs à TOUS les objets
    current = prime_obj(prime_att(frozenset()))

    while current is not None:
        extent = prime_att(current)
        concepts.append((current, extent))
        current = next_closure(current, n_att, prime_att, prime_obj)

    return concepts


# =============================================================================
# 4. CALCUL DES COUVERTURES DIRECTES (DIAGRAMME DE HASSE RÉDUIT)
#    Une arête i -> j existe ssi extent(j) ⊂ extent(i) sans intermédiaire.
# =============================================================================
def build_cover_relations(concepts_list):
    """
    Calcule les relations de couverture directe du treillis (Hasse réduit).
    Retourne covers : dict id_parent -> liste d'id_enfants.
    """
    n = len(concepts_list)
    extents = [c[1] for c in concepts_list]
    covers = {i: [] for i in range(n)}

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if not (extents[j] < extents[i]):
                continue
            # Vérifier l'absence d'intermédiaire strict
            is_direct = not any(
                extents[j] < extents[k] < extents[i]
                for k in range(n) if k != i and k != j
            )
            if is_direct:
                covers[i].append(j)

    return covers


# =============================================================================
# 5. ATTRIBUTS ET OBJETS PROPRES
#    Attributs propres : dans l'intension du concept, absents des intensions
#                        de tous ses parents directs.
#    Objets propres    : dans l'extension du concept, absents des extensions
#                        de tous ses enfants directs.
# =============================================================================
def compute_proper_attrs(concepts_list, covers):
    """Retourne un dict id -> frozenset d'indices d'attributs propres."""
    n = len(concepts_list)
    parents = {i: [] for i in range(n)}
    for parent, children in covers.items():
        for child in children:
            parents[child].append(parent)

    proper = {}
    for i, (intent, _) in enumerate(concepts_list):
        parent_attrs = set()
        for p in parents[i]:
            parent_attrs |= concepts_list[p][0]
        proper[i] = intent - parent_attrs
    return proper


def compute_proper_objs(concepts_list, covers):
    """Retourne un dict id -> frozenset d'indices d'objets propres."""
    proper = {}
    for i, (_, extent) in enumerate(concepts_list):
        child_objs = set()
        for child in covers[i]:
            child_objs |= concepts_list[child][1]
        proper[i] = extent - child_objs
    return proper


# =============================================================================
# 6. COLORIAGE DES NŒUDS
#    - lightblue : ni attributs propres ni objets propres
#    - orange    : concept avec le plus grand nombre d'objets propres
#                  (premier id en cas d'ex-æquo)
#    - None      : autres cas (blanc, style filled par défaut)
# =============================================================================
def compute_colors(n, proper_attrs, proper_objs):
    """Retourne un dict id -> fillcolor ('lightblue', 'orange', ou None)."""
    max_proper = -1
    median_id = None
    for i in range(n):
        nb = len(proper_objs[i])
        if nb > max_proper:
            max_proper = nb
            median_id = i

    colors = {}
    for i in range(n):
        has_attr = len(proper_attrs[i]) > 0
        has_obj  = len(proper_objs[i]) > 0
        if not has_attr and not has_obj:
            colors[i] = 'lightblue'
        elif i == median_id and max_proper > 0:
            colors[i] = 'orange'
        else:
            colors[i] = None
    return colors


# =============================================================================
# 7. GÉNÉRATION DU FICHIER DOT
# =============================================================================
def escape_dot(s):
    """Échappe les caractères spéciaux pour les labels record Graphviz."""
    for ch in ('\\', '"', '<', '>', '{', '}', '|'):
        s = s.replace(ch, '\\' + ch)
    return s


def generate_dot(path, concepts_list, covers, proper_attrs, proper_objs,
                 colors, attr_names, obj_names):
    """Écrit le fichier .dot représentant le diagramme de Hasse du treillis."""
    lines = ['digraph G {', '    rankdir=BT;']

    for i, (intent, extent) in enumerate(concepts_list):
        nb_intent = len(intent)
        nb_extent = len(extent)

        # Attributs propres triés par nom
        p_attrs = sorted(attr_names[a] for a in proper_attrs[i])
        attrs_str = '\\n'.join(escape_dot(a) for a in p_attrs)
        if attrs_str:
            attrs_str += '\\n'

        # Objets propres triés par nom
        p_objs = sorted(obj_names[o] for o in proper_objs[i])
        objs_str = '\\n'.join(escape_dot(o) for o in p_objs)
        if objs_str:
            objs_str += '\\n'

        label = f'{{{i} (I: {nb_intent}, E: {nb_extent})|{attrs_str}|{objs_str}}}'

        color = colors[i]
        if color:
            node_line = (f'{i} [shape=record,style=filled,fillcolor={color},'
                         f'label="{label}"];')
        else:
            node_line = f'{i} [shape=record,style=filled,label="{label}"];'

        lines.append(node_line)

    # Arêtes de couverture directe (parent -> enfant, rankdir=BT)
    for parent, children in covers.items():
        for child in children:
            lines.append(f'    {parent} -> {child}')

    lines.append('}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


# =============================================================================
# 8. POINT D'ENTRÉE PRINCIPAL
# =============================================================================
def main():
    if len(sys.argv) < 3:
        print("Usage : python lattice_builder.py <input.csv> <output.dot>")
        sys.exit(1)

    csv_path = sys.argv[1]
    dot_path = sys.argv[2]

    # --- Lecture du CSV ---
    print(f"Lecture du fichier CSV : {csv_path}")
    obj_names, attr_names, table = load_csv(csv_path)
    n_obj = len(obj_names)
    n_att = len(attr_names)
    print(f"  {n_obj} objets, {n_att} attributs.")

    # --- Construction du treillis (mesure CPU encadrée ici uniquement) ---
    print("Construction du treillis de Galois (algorithme Next Closure)...")
    t_start = time.process_time()

    concepts_list = build_concepts(n_obj, n_att, table)

    t_end = time.process_time()
    elapsed = t_end - t_start
    print(f"  {len(concepts_list)} concepts formels trouvés.")

    # --- Diagramme de Hasse ---
    print("Calcul des couvertures directes (diagramme de Hasse)...")
    covers = build_cover_relations(concepts_list)

    # --- Attributs et objets propres ---
    proper_attrs = compute_proper_attrs(concepts_list, covers)
    proper_objs  = compute_proper_objs(concepts_list, covers)

    # --- Coloriage ---
    colors = compute_colors(len(concepts_list), proper_attrs, proper_objs)

    # --- Génération du fichier DOT ---
    print(f"Génération du fichier DOT : {dot_path}")
    generate_dot(dot_path, concepts_list, covers, proper_attrs, proper_objs,
                 colors, attr_names, obj_names)
    print("Fichier DOT généré avec succès.")

    # --- Affichage du temps CPU ---
    print(f"\nTemps CPU de construction du treillis : {elapsed:.6f} secondes")


if __name__ == '__main__':
    main()