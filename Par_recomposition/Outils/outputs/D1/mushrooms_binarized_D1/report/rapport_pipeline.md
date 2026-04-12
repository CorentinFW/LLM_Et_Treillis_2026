# Rapport pipeline - mushrooms_binarized_D1

Généré le: 2026-04-11T13:00:16+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 1
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque = taille récursive maximale du répertoire de travail du dataset surveillé.
- I/O = volumes lus/écrits observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 26.88 MiB | 9.37 MiB | 1.33 MiB | 7.90 MiB |
| fca4j | 1 | 170.57 MiB | 1.84 MiB | 1.33 MiB | 32.00 KiB |
| gpt53_lattice | 1 | 25.52 MiB | 18.83 MiB | 1.33 MiB | 20.34 MiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mushrooms_binarized | fca4j | OK | 0.362 | 170.57 MiB | 1.84 MiB | 1.33 MiB | 32.00 KiB | no | yes |
| mushrooms_binarized | claude_lattice2 | OK | 13.742 | 26.88 MiB | 9.37 MiB | 1.33 MiB | 7.90 MiB | no | yes |
| mushrooms_binarized | gpt53_lattice | OK | 26.411 | 25.52 MiB | 18.83 MiB | 1.33 MiB | 20.34 MiB | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| mushrooms_binarized | fca4j | OK | converted to full | yes |
| mushrooms_binarized | claude_lattice2 | OK | converted to full | yes |
| mushrooms_binarized | gpt53_lattice | CONVERSION_FAILED | Erreur: Cardinalité d'extension incohérente pour le nœud '1': entête=8124, reconstruit=508 | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| mushrooms_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- mushrooms_binarized
  - claude_lattice2__vs__fca4j: True

