# Rapport pipeline - monks-1_binarized_D1

Généré le: 2026-04-11T12:59:08+02:00

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
| claude_lattice2 | 1 | 8.56 MiB | 40.07 KiB | 0 B | 0 B |
| fca4j | 1 | 37.17 MiB | 40.07 KiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 7.34 MiB | 19.82 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| monks-1_binarized | fca4j | OK | 0.131 | 37.17 MiB | 40.07 KiB | 0 B | 32.00 KiB | no | yes |
| monks-1_binarized | claude_lattice2 | OK | 0.076 | 8.56 MiB | 40.07 KiB | 0 B | 0 B | no | yes |
| monks-1_binarized | gpt53_lattice | FAILED | 0.068 | 7.34 MiB | 19.82 KiB | 0 B | 0 B | no | no |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| monks-1_binarized | fca4j | OK | converted to full | yes |
| monks-1_binarized | claude_lattice2 | OK | converted to full | yes |
| monks-1_binarized | gpt53_lattice | MISSING_RAW_DOT | raw DOT not available from execution stage | no |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| monks-1_binarized | claude_lattice2 vs fca4j | OK | true |

## Matrice d'équivalence

- monks-1_binarized
  - claude_lattice2__vs__fca4j: True

