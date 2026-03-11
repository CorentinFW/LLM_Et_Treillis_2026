# Rôle
Tu es un expert en Python, en analyse de graphes et en treillis formels représentés en fichiers Graphviz `.dot`.

# Contexte
Tu dois concevoir un algorithme Python général permettant de comparer deux fichiers `.dot` représentant des treillis.

Les deux fichiers à comparer sont :
- `FCA4J/Animals11/Lattice/full/Animals11.dot`
- `GPT-5.1/Animals11/Lattice/full/Animals11_full.dot`

Important :
- l’algorithme doit fonctionner sur ces deux fichiers ;
- mais il doit être conçu pour traiter des cas généraux, et pas seulement ces exemples précis ;
- il ne faut pas produire une solution ad hoc dépendante uniquement de la structure de ces deux fichiers.

# Objectif
Écris un algorithme en Python qui détermine si deux fichiers `.dot` décrivent le même treillis, à renumérotation des nœuds près.

Deux nœuds de fichiers différents doivent être considérés comme équivalents si leur contenu logique est identique, même si leur identifiant local diffère.

Ensuite, une fois les nœuds appariés, l’algorithme doit vérifier que les relations entre nœuds sont également identiques.

# Définition précise de l’équivalence entre nœuds
Chaque nœud contient un label de type similaire à :

`label="{1 (I: 1, E: 8)|flies|arctic-tern\\nbat\\ngreat-auk\\ngreater-flamingo\\nladybird\\nlittle-tern\\nsilver-gull\\nwood-pecker}"`

ou à :

`label="{1 (I: 1, E: 8)|flies\n|ladybird\nbat\ngreater-flamingo\nsilver-gull\nlittle-tern\ngreat-auk\nwood-pecker\narctic-tern\n}"`

Pour comparer deux nœuds, applique impérativement les règles suivantes :

1. Ignore l’identifiant local placé au début du label.
   - Exemple : dans `{1 (I: 1, E: 8)|...}`, le `1` initial ne doit pas être utilisé pour décider de l’équivalence.

2. Conserve la partie `(I: x, E: y)` comme partie intégrante de la signature logique.

3. Extrais les attributs et les objets du label.

4. Considère les attributs comme un ensemble.
   - Leur ordre d’apparition dans le fichier ne doit pas être considéré comme significatif.
   - Deux signatures sont équivalentes si elles contiennent exactement les mêmes attributs, même dans un ordre différent.

5. Considère les objets comme un ensemble.
   - Leur ordre d’apparition dans le fichier ne doit pas être considéré comme significatif.
   - Deux signatures sont équivalentes si elles contiennent exactement les mêmes objets, même dans un ordre différent.

6. Traite comme non significatives les différences de format suivantes :
   - séparateurs `|` ;
   - séquences `\n` ;
   - retours à la ligne réels ;
   - espaces superflus ;
   - ligne vide finale dans la partie objets ou attributs.

7. Deux nœuds sont équivalents si et seulement si :
   - leur partie `(I: x, E: y)` est identique ;
   - l’ensemble de leurs attributs est identique ;
   - l’ensemble de leurs objets est identique.

# Contraintes
Respecte impérativement les contraintes suivantes :

- Écris une solution en Python.
- Propose un algorithme robuste, clair et maintenable.
- La solution doit fonctionner sur des cas généraux.
- Ne suppose pas que les identifiants de nœuds sont les mêmes dans les deux fichiers.
- Ne compare pas les labels comme de simples chaînes brutes.
- Normalise les labels avant comparaison.
- Vérifie d’abord l’équivalence des nœuds, puis l’équivalence des arêtes.
- Gère explicitement les cas où un nœud d’un fichier n’a aucun équivalent dans l’autre.
- Gère explicitement les cas où plusieurs nœuds pourraient produire une ambiguïté de correspondance.
- Si une hypothèse est nécessaire, énonce-la explicitement.

# Tâches à effectuer
Suis exactement les étapes suivantes.

## Étape 1 — Décrire l’approche
Explique brièvement l’approche algorithmique retenue.

## Étape 2 — Définir une signature canonique de nœud
Définis une méthode de normalisation produisant, pour chaque nœud, une signature canonique indépendante de son identifiant local.

Cette signature doit reposer sur :
- `(I: x, E: y)`
- l’ensemble trié des attributs
- l’ensemble trié des objets

Par exemple, une signature canonique peut prendre la forme :

`(I: x, E: y)|attr1,attr2,...|obj1,obj2,...`

L’objectif de cette canonicalisation est de rendre deux nœuds équivalents comparables même si :
- leur identifiant local diffère ;
- l’ordre des attributs diffère ;
- l’ordre des objets diffère ;
- la mise en forme du label diffère.

## Étape 3 — Parser les fichiers `.dot`
Écris le code Python nécessaire pour :
- lire un fichier `.dot` ;
- extraire tous les nœuds ;
- extraire tous les arcs `a -> b` ;
- associer à chaque identifiant local de nœud sa signature canonique.

Le parsing doit être suffisamment robuste pour supporter des variantes raisonnables de formatage.

## Étape 4 — Construire la correspondance entre les nœuds
Construit une table de correspondance entre les nœuds du fichier 1 et ceux du fichier 2 à partir de leur signature canonique.

La table doit associer :
- un identifiant commun généré ;
- l’identifiant du nœud dans le fichier 1 ;
- l’identifiant du nœud dans le fichier 2.

Exemple de structure attendue :

| Commun | fichier1 | fichier2 |
|--------|----------|----------|
| C1 | 1 | 1 |
| C2 | 4 | 7 |

Si une signature n’existe que dans un seul fichier, signale-la explicitement.

## Étape 5 — Comparer les arêtes
Après avoir établi la correspondance entre nœuds :
- transforme les arêtes de chaque fichier en arêtes entre identifiants communs ;
- compare les ensembles d’arêtes normalisées ;
- détermine si la structure relationnelle des deux treillis est identique.

## Étape 6 — Produire le code Python complet
Fournis un code Python complet, exécutable et structuré.

Le code doit être organisé de manière modulaire, par exemple avec des fonctions du type :
- lecture du fichier ;
- extraction des nœuds ;
- normalisation des labels ;
- construction des signatures ;
- construction de la table de correspondance ;
- comparaison des arêtes ;
- fonction principale.

## Étape 7 — Expliquer le résultat attendu
Explique brièvement ce que le programme doit afficher ou retourner.

# Format de sortie attendu
Ta réponse doit respecter exactement la structure suivante :

## 1. Approche
Donne un résumé court de la stratégie.

## 2. Hypothèses
Liste les hypothèses explicites retenues.

## 3. Algorithme
Décris les étapes principales de l’algorithme.

## 4. Code Python
Fournis le code Python complet.

## 5. Sortie attendue
Explique le format de sortie produit par le programme, par exemple :
- verdict d’équivalence ;
- nœuds non appariés ;
- table de correspondance ;
- arêtes présentes dans un fichier mais pas dans l’autre.

# Exigences de qualité
- Utilise des noms de variables et de fonctions explicites.
- Commente les parties délicates du code.
- Évite les raccourcis fragiles.
- Préfère une logique claire à une logique compacte mais obscure.
- Assure-toi que le code peut être réutilisé sur d’autres fichiers `.dot` de même nature.

# Instruction finale
Écris maintenant la solution complète en Python pour comparer de manière générale deux treillis décrits par des fichiers `.dot`, en respectant strictement toutes les consignes ci-dessus.