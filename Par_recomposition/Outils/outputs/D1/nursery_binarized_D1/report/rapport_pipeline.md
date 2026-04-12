# Rapport pipeline - nursery_binarized_D1

Généré le: 2026-04-11T13:07:18+02:00

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
| claude_lattice2 | 1 | 15.71 MiB | 1.47 MiB | 752.00 KiB | 1.52 MiB |
| fca4j | 1 | 70.48 MiB | 1.47 MiB | 752.00 KiB | 796.00 KiB |
| gpt53_lattice | 1 | 8.46 MiB | 748.96 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nursery_binarized | fca4j | OK | 0.202 | 70.48 MiB | 1.47 MiB | 752.00 KiB | 796.00 KiB | no | yes |
| nursery_binarized | claude_lattice2 | OK | 0.133 | 15.71 MiB | 1.47 MiB | 752.00 KiB | 1.52 MiB | no | yes |
| nursery_binarized | gpt53_lattice | FAILED | 0.076 | 8.46 MiB | 748.96 KiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| nursery_binarized | fca4j | OK | converted to full | yes |
| nursery_binarized | claude_lattice2 | OK | converted to full | yes |
| nursery_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| nursery_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- nursery_binarized
  - claude_lattice2__vs__fca4j: True

