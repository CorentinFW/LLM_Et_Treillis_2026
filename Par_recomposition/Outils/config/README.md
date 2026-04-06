# Configuration du pipeline

Le pipeline lit trois fichiers JSON dans ce dossier.

## Fichiers

1. algorithms.json
- Liste des algorithmes testables.
- Chaque algorithme définit:
  - id
  - label
  - csv_path_template
  - command_template
  - dot_glob_template
  - timeout_seconds

2. datasets.json
- Liste des datasets.
- Chaque dataset définit:
  - id
  - label
  - tags

3. run.json
- Sélection et politique de run.
- Champs:
  - selected_algorithms
  - selected_datasets
  - stages
  - timeout_seconds
  - continue_on_error

## Placeholders disponibles dans templates

- {repo_root}
- {dataset_id}
- {dataset_label}
- {csv_path} (uniquement dans command_template)

## Ajouter un nouvel algorithme

1. Ajouter une entrée dans algorithms.json.
2. Donner la commande complète dans command_template.
3. Définir un dot_glob_template qui correspond au DOT produit.

## Ajouter un nouveau dataset

1. Ajouter une entrée dans datasets.json.
2. Vérifier que les chemins csv_path_template de chaque algorithme pointent vers un CSV existant pour ce dataset.
