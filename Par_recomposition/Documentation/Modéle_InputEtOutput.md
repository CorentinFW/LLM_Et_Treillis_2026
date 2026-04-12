# Modèle Input/Output FCA - Méthode et Justification

## 1. Version clarifiée des consignes

Objectif reformulé pour éviter toute ambiguïté:

1. Inspecter tous les fichiers CSV présents dans le workspace.
2. Extraire leur structure exacte (separateur, en-tete, type de colonnes, contraintes de valeurs).
3. Produire une generalisation robuste permettant a un LLM d'ecrire un lecteur compatible avec tous les cas observes.
4. Inspecter les fichiers DOT produits par FCA4J et nommes comme des sorties de lattice (`<nom_dataset>.dot`).
5. Extraire leur structure exacte (syntaxe graphe, format des noeuds, format des aretes, etiquettes).
6. Produire une generalisation robuste permettant a un LLM d'ecrire un generateur DOT equivalent.
7. Revalider explicitement que la generalisation couvre tous les exemples disponibles, et documenter les exceptions.

## 2. Perimetre verifie

### CSV

- 62 fichiers CSV inspectes dans tout le workspace.
- 18 jeux de donnees distincts (plusieurs copies identiques selon dossiers).
- Duplications confirmees coherentes (meme structure et contenus par dataset, hors repertoire).

### DOT FCA4J

- 30 fichiers `.dot` dans `FCA4J`.
- Cible analysee: fichiers de type `Lattice/<dataset>.dot` (et `Lattice/full/Animals11.dot` car meme convention de nommage).
- 20 fichiers cibles structures examines (incluant un cas volumineux `bank_binarized.dot`).

## 3. Raisons utilisees pour construire le contexte final

Le document `Documentation/Contexte_Input_Output` est base sur des invariants observes, et non sur des suppositions:

1. **Invariants CSV confirms sur 62/62 fichiers**:
   - Colonnes de donnees binaires (`0`/`1`) a partir de la colonne 2.
   - Nombre de colonnes constant sur toutes les lignes d'un meme fichier.
   - Premiere cellule d'en-tete vide (ou `""` pour le cas `mushrooms_binarized.csv`).

2. **Variantes CSV prises en compte**:
   - Deux separateurs observes: `;` et `,`.
   - Presence possible de guillemets autour des champs (cas `mushrooms_binarized.csv`).
   - Identifiant ligne (colonne 1) parfois textuel (`ladybird`, `o1`), parfois numerique (`0`, `data_1`).

3. **Invariants DOT confirms sur sorties FCA4J**:
   - Envelope Graphviz stable: `digraph G {`, `rankdir=BT;`, `}`.
   - Noms de noeuds entiers (`0`, `1`, ...).
   - Etiquettes de noeuds en `shape=record` avec schema `{id (I: x, E: y)|intent|extent}`.
   - Aretes dirigees de forme `u -> v`.

4. **Variantes DOT prises en compte**:
   - Cas degenerate valide: graphe minimal sans arete (1 seul noeud) ou vide logique (`digraph G` + `rankdir` + fermeture).
   - Couleurs de noeuds optionnelles (`fillcolor=lightblue`, `fillcolor=orange`, ou aucune).
   - Extent pouvant contenir des IDs d'objets ou des lignes CSV brutes tres longues (cas single-node massif).

5. **Exception importante detectee et documentee**:
   - `FCA4J/eg80_80/Lattice/eg80_80.dot` est un fichier vide (0 octet), non conforme a la syntaxe DOT.
   - La generalisation precise donc la difference entre:
     - sortie DOT valide minimale,
     - fichier vide (etat d'echec / generation incomplete).

## 4. Strategie de generalisation retenue

Le modele final est volontairement **contraint et operationnel**:

- Cote input CSV: lecteur tolerant (separateur auto, guillemets, encodage), mais validation stricte du binaire et de la largeur des lignes.
- Cote output DOT: ecriture canonique d'un sous-ensemble stable de Graphviz, suffisant pour reproduire la structure attendue par les outils du projet.
- Distinction explicite entre champs obligatoires, optionnels et cas limites.

## 5. Reverification post-generalisation

La generalisation du document `Documentation/Contexte_Input_Output` a ete reverifiee contre les exemples disponibles:

- **CSV**: couverture complete des 62 fichiers (aucune violation des regles generalisees).
- **DOT FCA4J cibles**: couverture complete des structures observees (grands graphes, graphes compacts, graphes single-node, graphe minimal vide logique).
- **Anomalie hors-spec**: seul `eg80_80.dot` (0 octet) sort du format DOT valide; il est conserve comme cas d'echec a detecter.

## 6. Resultat attendu

Le fichier `Documentation/Contexte_Input_Output` peut etre utilise comme reference de generation/validation pour des LLM afin de:

- produire un parseur CSV compatible avec tous les datasets du projet,
- produire des fichiers DOT equivalant structurellement aux sorties FCA4J attendues.
