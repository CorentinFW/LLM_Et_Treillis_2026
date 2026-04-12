# Rapport pipeline - connect-4_binarized_D1

Généré le: 2026-04-11T12:57:50+02:00

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
| claude_lattice2 | 1 | 61.78 MiB | 51.25 MiB | 16.01 MiB | 17.20 MiB |
| fca4j | 1 | 275.67 MiB | 34.06 MiB | 16.07 MiB | 32.00 KiB |
| gpt53_lattice | 1 | 8.59 MiB | 17.00 MiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| connect-4_binarized | fca4j | OK | 0.365 | 275.67 MiB | 34.06 MiB | 16.07 MiB | 32.00 KiB | no | yes |
| connect-4_binarized | claude_lattice2 | OK | 0.473 | 61.78 MiB | 51.25 MiB | 16.01 MiB | 17.20 MiB | no | yes |
| connect-4_binarized | gpt53_lattice | FAILED | 0.075 | 8.59 MiB | 17.00 MiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| connect-4_binarized | fca4j | OK | converted to full | yes |
| connect-4_binarized | claude_lattice2 | OK | converted to full | yes |
| connect-4_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| connect-4_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- connect-4_binarized
  - claude_lattice2__vs__fca4j: True

