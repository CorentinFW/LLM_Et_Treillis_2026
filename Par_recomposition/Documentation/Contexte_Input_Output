# Contexte Input/Output de reference (FCA)

## 1. Input CSV attendu

## 1.1 Structure canonique

Un CSV de contexte formel est interprete comme:

- Ligne 1: en-tete des attributs.
- Colonne 1: identifiant objet (nom de l'objet / ID de ligne).
- Colonnes 2..N: attributs binaires (`0` ou `1`).

Forme logique:

- En-tete: `[cellule_vide, attr_1, attr_2, ..., attr_k]`
- Ligne i: `[obj_i, b_1, b_2, ..., b_k]` avec `b_j in {0,1}`

## 1.2 Invariants obligatoires

1. Nombre de colonnes constant sur toutes les lignes.
2. Toutes les valeurs des colonnes 2..N sont binaires (`0` ou `1`).
3. Au moins une ligne d'en-tete et une ligne de donnees.
4. La premiere cellule d'en-tete est vide (`""` autorise).

## 1.3 Variantes autorisees observees

1. Separateur `;` ou `,`.
2. Champs quotes (`"value"`) possibles.
3. Identifiants objets textuels ou numeriques.
4. Noms d'attributs libres (lettres, chiffres, tirets, underscores, espaces, apostrophes, etc.).

## 1.4 Regles de lecture robustes (pour LLM)

1. Detecter le separateur automatiquement entre `;` et `,`.
2. Parser en mode CSV standard (gestion des guillemets).
3. Normaliser les cellules (trim espaces externes; enlever guillemets externes).
4. Lire `object_name = colonne_1`.
5. Lire `attributes = colonnes_2..N`.
6. Valider que chaque attribut est `0` ou `1`.
7. Construire le contexte formel:
   - `Objects = [object_name_i]`
   - `Attributes = [attr_j]`
   - `Incidence(i,j) = 1 si valeur == "1", sinon 0`

## 1.5 Exemples minimaux valides

Exemple `;`:

```csv
;a1;a2;a3
o1;1;0;1
o2;0;1;1
```

Exemple `,`:

```csv
,attr_x,attr_y
obj_1,1,0
obj_2,0,1
```

## 1.6 Cas reel particulier a couvrir

- `mushrooms_binarized.csv`: separateur `;` + champs quotes (`"";"attr";...`).

## 2. Output DOT attendu (style FCA4J)

## 2.1 Envelope DOT canonique

Un fichier DOT valide doit suivre cette ossature:

```dot
digraph G {
    rankdir=BT;
    ... definitions de noeuds ...
    ... aretes ...
}
```

- Graphe dirige (`digraph`).
- Orientation bas-vers-haut (`rankdir=BT`).

## 2.2 Format des noeuds

Chaque noeud utilise un ID entier et une etiquette record:

```dot
<ID> [shape=record,style=filled[,fillcolor=<color>],label="{<ID> (I: <intent_size>, E: <extent_size>)|<intent_lines>|<extent_lines>}"];
```

Contraintes:

1. `<ID>` est un entier unique (`0`, `1`, ...).
2. Les tailles `I` et `E` sont des entiers >= 0.
3. Le label est au format record a 3 blocs:
   - bloc 1: metadonnees du concept,
   - bloc 2: intent (attributs, separes par `\\n`),
   - bloc 3: extent (objets ou IDs, separes par `\\n`).
4. `fillcolor` est optionnel.

Couleurs observees:

- `fillcolor=lightblue`
- `fillcolor=orange`
- ou aucune couleur explicite.

## 2.3 Format des aretes

```dot
<source_id> -> <target_id>
```

- IDs entiers existants.
- Aretes dirigees.
- Le point-virgule final peut etre omis (observe dans les sorties FCA4J analysees).

## 2.4 Cas limites valides a reproduire

1. Graphe avec plusieurs noeuds + aretes (cas general).
2. Graphe a un seul noeud, sans arete (cas de lattice reduit).
3. Graphe minimal logique sans noeud:

```dot
digraph G {
    rankdir=BT;
}
```

## 2.5 Cas d'echec a detecter (hors format)

- Fichier vide (0 octet), ex: `FCA4J/eg80_80/Lattice/eg80_80.dot`.
- Ce cas n'est pas un DOT valide et doit etre traite comme echec de generation, pas comme format de sortie normal.

## 2.6 Regles d'ecriture robustes (pour LLM)

1. Toujours ecrire `digraph G {` puis `rankdir=BT;`.
2. Emettre tous les noeuds avant les aretes.
3. Conserver des IDs entiers compacts si possible (`0..n-1`).
4. Encoder intent/extent en lignes separees par `\\n` dans le label record.
5. Echapper correctement les caracteres speciaux de label DOT (`"`, `\\`).
6. Fermer par `}`.

## 3. Contrat I/O exploitable pour generation automatique

## 3.1 Contrat Input (CSV -> contexte)

Entree attendue:

- `path_csv`
- `delimiter in {",",";"}` (auto-detecte si non fourni)

Sortie interne attendue:

- `objects: list[str]`
- `attributes: list[str]`
- `matrix: list[list[int]]` (valeurs 0/1)

Preconditions:

- largeur de ligne constante,
- colonnes 2..N binaires.

## 3.2 Contrat Output (lattice -> DOT)

Entree attendue:

- `concepts`: liste de concepts avec:
  - `id: int`
  - `intent: list[str]`
  - `extent: list[str]`
  - `intent_size: int`
  - `extent_size: int`
  - `fillcolor: optional[str]`
- `covers`: liste d'aretes `(u,v)`.

Sortie fichier:

- DOT syntaxiquement valide,
- structure conforme sections 2.1 a 2.4.

## 4. Validation de conformite (checklist rapide)

Pour un CSV:

1. Separateur detecte correctement.
2. Colonne 1 = identifiant objet.
3. Colonnes 2..N toutes binaires.
4. Pas de ligne avec nombre de colonnes different.

Pour un DOT genere:

1. `digraph G {` present.
2. `rankdir=BT;` present.
3. Tous les noeuds ont un label record `{id (I: x, E: y)|...|...}`.
4. Toutes les aretes referencent des IDs existants.
5. Fichier non vide.
6. Fermeture `}` presente.
