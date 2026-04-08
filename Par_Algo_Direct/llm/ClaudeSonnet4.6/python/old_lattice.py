# =============================================================================
# Fichier      : lattice_builder.py
# Objectif     : Construction d'un treillis de Galois (Analyse Formelle de
#                Concepts) à partir d'un fichier CSV binaire, et génération
#                d'un fichier DOT (Graphviz) représentant le diagramme de Hasse.
# Bibliothèque : concepts  (Formal Concept Analysis en Python)
# Installation : pip install concepts
# Exemple      : python lattice_builder.py Animals11.csv Animals11_out.dot
# =============================================================================

import sys
import time
import csv

# La bibliothèque "concepts" fournit une implémentation complète de l'AFC,
# incluant la construction du treillis de Galois en une seule passe.
try:
    import concepts
except ImportError:
    print("Erreur : la bibliothèque 'concepts' n'est pas installée.")
    print("Installez-la avec : pip install concepts")
    sys.exit(1)


# =============================================================================
# 1. LECTURE DU FICHIER CSV
#    Format attendu : séparateur ";", première colonne = noms des objets,
#    colonnes suivantes = attributs binaires (0 ou 1), avec ligne d'en-tête.
# =============================================================================
def load_csv(path):
    """Lit le fichier CSV et retourne (objets, attributs, matrice booléenne)."""
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader)

        # La première colonne est le nom des objets (sans en-tête significatif)
        attr_names = header[1:]  # noms des attributs

        objects = []
        bools = []
        for row in reader:
            if not row:
                continue
            objects.append(row[0])
            bools.append(tuple(bool(int(v)) for v in row[1:]))

    return objects, attr_names, bools


# =============================================================================
# 2. CONSTRUCTION DU TREILLIS DE GALOIS EN UNE SEULE PASSE
#    On utilise la bibliothèque "concepts" qui construit l'ensemble complet
#    des concepts formels et leur ordre partiel en un seul parcours global
#    du contexte formel (algorithme In-Close ou Next-Closure interne).
# =============================================================================
def build_lattice(objects, attr_names, bools):
    """
    Construit le contexte formel et le treillis de Galois.
    Retourne le contexte et le treillis.
    Mesure le temps CPU de construction uniquement.
    """
    # Création du contexte formel (objet concepts.Context)
    context = concepts.Context(objects, attr_names, bools)

    # --- Début de la mesure du temps CPU ---
    t_start = time.process_time()

    # Construction du treillis en une seule passe (appel interne à l'algo AFC)
    lattice = context.lattice

    # --- Fin de la mesure du temps CPU ---
    t_end = time.process_time()

    elapsed = t_end - t_start
    return context, lattice, elapsed


# =============================================================================
# 3. UTILITAIRES POUR LE DIAGRAMME DE HASSE
#    - Extraction des attributs/objets "propres" à chaque concept.
#    - Calcul des relations de couverture directe.
# =============================================================================

def get_concept_list(lattice):
    """
    Retourne la liste ordonnée des concepts du treillis.
    Chaque concept expose .extent (objets) et .intent (attributs).
    """
    return list(lattice)


def build_cover_relations(concepts_list):
    """
    Calcule les relations de couverture directe du treillis (diagramme de Hasse
    réduit). Retourne un dict : id_parent -> liste d'id_enfants couverts.

    La relation de couverture A > B signifie que B est directement en dessous
    de A (A -> B dans le DOT avec rankdir=BT).
    """
    n = len(concepts_list)

    # Index rapide : frozenset(extent) -> id
    extent_to_id = {frozenset(c.extent): i for i, c in enumerate(concepts_list)}

    # Pré-calcul des ensembles d'extension pour comparaison rapide
    extents = [frozenset(c.extent) for c in concepts_list]

    # Pour chaque concept, trouver ses successeurs directs (couvertures)
    # A couvre B  <=>  extents[B] ⊂ extents[A]  ET  il n'existe pas C tel que
    #                  extents[B] ⊂ extents[C] ⊂ extents[A]
    covers = {i: [] for i in range(n)}  # parent -> enfants directs

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # B (j) doit être strictement inclus dans A (i)
            if not (extents[j] < extents[i]):
                continue
            # Vérifier qu'il n'existe pas d'intermédiaire
            is_direct = True
            for k in range(n):
                if k == i or k == j:
                    continue
                if extents[j] < extents[k] < extents[i]:
                    is_direct = False
                    break
            if is_direct:
                covers[i].append(j)

    return covers


def compute_proper_attributes(concepts_list, covers):
    """
    Calcule les attributs propres de chaque concept :
    attributs présents dans son intension mais absents de l'intension
    de tous ses parents directs dans le treillis.
    """
    n = len(concepts_list)
    # Pour chaque concept, retrouver ses parents directs
    # (le concept i est parent de j si j est dans covers[i])
    parents = {i: [] for i in range(n)}
    for parent, children in covers.items():
        for child in children:
            parents[child].append(parent)

    proper_attrs = {}
    for i, c in enumerate(concepts_list):
        intent_i = set(c.intent)
        # Union des intensions de tous les parents directs
        parent_attrs = set()
        for p in parents[i]:
            parent_attrs |= set(concepts_list[p].intent)
        proper_attrs[i] = intent_i - parent_attrs

    return proper_attrs


def compute_proper_objects(concepts_list, covers):
    """
    Calcule les objets propres de chaque concept :
    objets présents dans son extension mais absents de l'extension
    de tous ses enfants directs dans le treillis.
    """
    proper_objs = {}
    for i, c in enumerate(concepts_list):
        extent_i = set(c.extent)
        # Union des extensions des enfants directs
        child_objs = set()
        for child in covers[i]:
            child_objs |= set(concepts_list[child].extent)
        proper_objs[i] = extent_i - child_objs

    return proper_objs


# =============================================================================
# 4. COLORIAGE DES NŒUDS
#    - lightblue : ni objets propres, ni attributs propres.
#    - orange    : concept médian (le plus grand nombre d'objets propres ;
#                  en cas d'ex-æquo, le premier par id).
#    - défaut    : autres cas.
# =============================================================================
def compute_colors(n, proper_attrs, proper_objs):
    """Retourne un dict id -> fillcolor ('lightblue', 'orange', ou None)."""
    colors = {}

    # Identifier le concept médian (max d'objets propres)
    max_proper = -1
    median_id = None
    for i in range(n):
        nb = len(proper_objs[i])
        if nb > max_proper:
            max_proper = nb
            median_id = i

    for i in range(n):
        has_attr = len(proper_attrs[i]) > 0
        has_obj  = len(proper_objs[i]) > 0
        if not has_attr and not has_obj:
            colors[i] = 'lightblue'
        elif i == median_id and max_proper > 0:
            colors[i] = 'orange'
        else:
            colors[i] = None  # défaut (blanc)

    return colors


# =============================================================================
# 5. GÉNÉRATION DU FICHIER DOT
#    Format Graphviz avec rankdir=BT, nœuds au format record, arêtes de
#    couverture directe uniquement.
# =============================================================================
def generate_dot(path, concepts_list, covers, proper_attrs, proper_objs, colors):
    """Écrit le fichier .dot représentant le diagramme de Hasse du treillis."""

    def escape_dot(s):
        """Échappe les caractères spéciaux pour les labels DOT."""
        return s.replace('\\', '\\\\').replace('"', '\\"').replace('<', '\\<').replace('>', '\\>').replace('{', '\\{').replace('}', '\\}').replace('|', '\\|')

    lines = ['digraph G {', '    rankdir=BT;']

    for i, c in enumerate(concepts_list):
        nb_intent = len(c.intent)
        nb_extent = len(c.extent)

        # Construction du label au format record
        # "{<id> (I: <nb>, E: <nb>)|<attributs>|<objets>}"
        attrs_str = '\\n'.join(escape_dot(a) for a in sorted(proper_attrs[i]))
        if attrs_str:
            attrs_str += '\\n'

        objs_str = '\\n'.join(escape_dot(o) for o in sorted(proper_objs[i]))
        if objs_str:
            objs_str += '\\n'

        label = f'{{{i} (I: {nb_intent}, E: {nb_extent})|{attrs_str}|{objs_str}}}'

        # Coloriage
        color = colors[i]
        if color:
            node_line = (f'{i} [shape=record,style=filled,fillcolor={color},'
                         f'label="{label}"];')
        else:
            node_line = f'{i} [shape=record,style=filled,label="{label}"];'

        lines.append(node_line)

    # Arêtes de couverture directe : parent -> enfant (rankdir=BT => enfant en bas)
    for parent, children in covers.items():
        for child in children:
            lines.append(f'    {parent} -> {child}')

    lines.append('}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


# =============================================================================
# 6. POINT D'ENTRÉE PRINCIPAL
# =============================================================================
def main():
    if len(sys.argv) < 3:
        print("Usage : python lattice_builder.py <input.csv> <output.dot>")
        sys.exit(1)

    csv_path = sys.argv[1]
    dot_path = sys.argv[2]

    # --- Lecture du CSV ---
    print(f"Lecture du fichier CSV : {csv_path}")
    objects, attr_names, bools = load_csv(csv_path)
    print(f"  {len(objects)} objets, {len(attr_names)} attributs.")

    # --- Construction du treillis (avec mesure du temps CPU) ---
    print("Construction du treillis de Galois...")
    context, lattice, elapsed = build_lattice(objects, attr_names, bools)

    # --- Extraction des concepts ---
    concepts_list = get_concept_list(lattice)
    print(f"  {len(concepts_list)} concepts formels trouvés.")

    # --- Calcul des couvertures directes (Hasse) ---
    print("Calcul du diagramme de Hasse (couvertures directes)...")
    covers = build_cover_relations(concepts_list)

    # --- Attributs et objets propres ---
    proper_attrs = compute_proper_attributes(concepts_list, covers)
    proper_objs  = compute_proper_objects(concepts_list, covers)

    # --- Coloriage ---
    colors = compute_colors(len(concepts_list), proper_attrs, proper_objs)

    # --- Génération du fichier DOT ---
    print(f"Génération du fichier DOT : {dot_path}")
    generate_dot(dot_path, concepts_list, covers, proper_attrs, proper_objs, colors)
    print("Fichier DOT généré avec succès.")

    # --- Affichage du temps CPU ---
    print(f"\nTemps CPU de construction du treillis : {elapsed:.6f} secondes")


if __name__ == '__main__':
    main()