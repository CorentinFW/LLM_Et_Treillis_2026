# Script de Benchmark pour Lattices

## Description

Le script `run_benchmark.sh` exécute un fichier C++ compilé sur tous les fichiers CSV d'un dossier et mesure les performances (temps d'exécution, utilisation RAM, utilisation disque).

## Caractéristiques

- ✓ Exécute l'exécutable sur chaque fichier CSV du dossier
- ✓ Place chaque sortie dans le même dossier que le CSV correspondant
- ✓ Mesure le temps d'exécution, la RAM max utilisée et la taille du fichier de sortie
- ✓ Timeout de 1 heure par test (configurable)
- ✓ Enregistre tous les résultats dans un fichier `Benchmark_<nom_dossier_executable>.txt`
- ✓ Note les timeouts et erreurs dans le rapport
- ✓ Génère un résumé final avec statistiques

## Usage

```bash
./run_benchmark.sh <chemin_executable> <dossier_csv>
```

### Exemples

```bash
# Exécuter un lattice sur les données de balance-scale
./run_benchmark.sh ./lattice ../Test/RealData/balance-scale_binarized/

# Exécuter un executable situé ailleurs
./run_benchmark.sh ../llm/ClaudeSonnet4.6/c++/lattice ../a\ copier/RealData/
```

## Résultats

Le script crée un fichier `Benchmark_<nom_dossier>.txt` contenant:

1. **Tableau détaillé**: Pour chaque CSV traité:
   - Nom du fichier
   - Temps d'exécution
   - RAM maximale utilisée (MB)
   - Taille du fichier de sortie (MB)
   - Statut (SUCCESS, TIMEOUT, ERROR)
   - Timestamp

2. **Résumé final**: Statistiques globales
   - Total de tests
   - Nombre réussis
   - Nombre de timeouts
   - Nombre d'erreurs

## Format du rapport

```
===============================================================================
RAPPORT DE BENCHMARK
===============================================================================
Format: nom_csv | temps(s) | RAM_max(MB) | disque_sortie(MB) | statut | timestamp

file1.csv | 2m30.45s | 256 | 4.2 | SUCCESS | 2026-05-08 14:30:45
file2.csv | >3600s | 512 | 8.1 | TIMEOUT (>3600s) | 2026-05-08 15:31:50
file3.csv | 1m45.23s | 128 | 2.5 | SUCCESS | 2026-05-08 16:17:15

================================================================================
RÉSUMÉ FINAL
================================================================================
Date de fin: 2026-05-08 16:25:30
Total de tests: 3
Réussis: 2
Timeouts: 1
Erreurs: 0
```

## Notes importantes

1. **Timeout**: Par défaut 1 heure (3600 secondes). Les tests qui dépassent ce délai sont arrêtés et marqués comme TIMEOUT.

2. **Sortie**: Chaque fichier CSV génère un fichier `.dot` dans le même dossier.

3. **RAM**: Mesurée en MB (utilisation maximale du processus).

4. **Permissions**: L'exécutable doit avoir les permissions d'exécution.

## Compatibilité

- Linux/Unix
- Nécessite `/usr/bin/time` pour la mesure détaillée des ressources
- Compatible avec les différentes distributions Linux

## Modifications possibles

Si vous souhaitez ajuster le timeout:
- Ouvrez le script et modifiez `TIMEOUT_SECONDS=3600` (ligne 16)
- 3600 = 1 heure, 1800 = 30 minutes, 7200 = 2 heures, etc.
