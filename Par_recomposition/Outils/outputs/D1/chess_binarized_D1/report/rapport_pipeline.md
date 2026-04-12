# Rapport pipeline - chess_binarized_D1

Généré le: 2026-04-11T12:56:48+02:00

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
| claude_lattice2 | 1 | 15.86 MiB | 1.38 MiB | 472.00 KiB | 956.00 KiB |
| fca4j | 1 | 57.47 MiB | 1.38 MiB | 472.00 KiB | 208.00 KiB |
| gpt53_lattice | 1 | 7.20 MiB | 944.25 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chess_binarized | fca4j | OK | 0.199 | 57.47 MiB | 1.38 MiB | 472.00 KiB | 208.00 KiB | no | yes |
| chess_binarized | claude_lattice2 | OK | 0.135 | 15.86 MiB | 1.38 MiB | 472.00 KiB | 956.00 KiB | no | yes |
| chess_binarized | gpt53_lattice | FAILED | 0.068 | 7.20 MiB | 944.25 KiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| chess_binarized | fca4j | OK | converted to full | yes |
| chess_binarized | claude_lattice2 | OK | converted to full | yes |
| chess_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| chess_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- chess_binarized
  - claude_lattice2__vs__fca4j: True

