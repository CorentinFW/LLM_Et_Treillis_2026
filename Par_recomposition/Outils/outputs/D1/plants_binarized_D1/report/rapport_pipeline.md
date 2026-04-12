# Rapport pipeline - plants_binarized_D1

Généré le: 2026-04-11T13:07:52+02:00

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
| claude_lattice2 | 1 | 36.26 MiB | 16.30 MiB | 5.33 MiB | 5.49 MiB |
| fca4j | 1 | 138.31 MiB | 10.81 MiB | 5.39 MiB | 32.00 KiB |
| gpt53_lattice | 1 | 7.05 MiB | 5.39 MiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plants_binarized | fca4j | OK | 0.257 | 138.31 MiB | 10.81 MiB | 5.39 MiB | 32.00 KiB | no | yes |
| plants_binarized | claude_lattice2 | OK | 0.25 | 36.26 MiB | 16.30 MiB | 5.33 MiB | 5.49 MiB | no | yes |
| plants_binarized | gpt53_lattice | FAILED | 0.068 | 7.05 MiB | 5.39 MiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| plants_binarized | fca4j | OK | converted to full | yes |
| plants_binarized | claude_lattice2 | OK | converted to full | yes |
| plants_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| plants_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- plants_binarized
  - claude_lattice2__vs__fca4j: True

