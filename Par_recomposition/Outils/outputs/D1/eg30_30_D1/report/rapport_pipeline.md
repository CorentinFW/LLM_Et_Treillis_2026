# Rapport pipeline - eg30_30_D1

Généré le: 2026-04-11T10:26:35+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 3
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque = taille récursive maximale du répertoire de travail du dataset surveillé.
- I/O = volumes lus/écrits observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 16.32 MiB | 3.51 MiB | 0 B | 416.00 KiB |
| fca4j | 1 | 143.89 MiB | 1.28 MiB | 56.00 KiB | 600.00 KiB |
| gpt53_lattice | 1 | 18.86 MiB | 4.27 MiB | 16.00 KiB | 2.77 MiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg30_30 | fca4j | OK | 0.321 | 143.89 MiB | 1.28 MiB | 56.00 KiB | 600.00 KiB | no | yes |
| eg30_30 | claude_lattice2 | OK | 0.595 | 16.32 MiB | 3.51 MiB | 0 B | 416.00 KiB | no | yes |
| eg30_30 | gpt53_lattice | OK | 9.287 | 18.86 MiB | 4.27 MiB | 16.00 KiB | 2.77 MiB | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg30_30 | fca4j | OK | converted to full | yes |
| eg30_30 | claude_lattice2 | OK | converted to full | yes |
| eg30_30 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg30_30 | claude_lattice2 vs fca4j | OK | true |
| eg30_30 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg30_30 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg30_30
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

