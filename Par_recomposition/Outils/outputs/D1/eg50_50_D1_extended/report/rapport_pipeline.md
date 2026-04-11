# Rapport pipeline - eg50_50_D1_extended

Généré le: 2026-04-11T12:01:41+02:00

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
| claude_lattice2 | 1 | 100.05 MiB | 21.03 MiB | 0 B | 21.36 MiB |
| fca4j | 1 | 822.12 MiB | 13.81 MiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 32.42 MiB | 56.21 MiB | 16.00 KiB | 68.04 GiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg50_50 | fca4j | OK | 3.075 | 822.12 MiB | 13.81 MiB | 0 B | 32.00 KiB | no | yes |
| eg50_50 | claude_lattice2 | OK | 175.97 | 100.05 MiB | 21.03 MiB | 0 B | 21.36 MiB | no | yes |
| eg50_50 | gpt53_lattice | OK | 3515.269 | 32.42 MiB | 56.21 MiB | 16.00 KiB | 68.04 GiB | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg50_50 | fca4j | OK | converted to full | yes |
| eg50_50 | claude_lattice2 | OK | converted to full | yes |
| eg50_50 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg50_50 | claude_lattice2 vs fca4j | OK | true |
| eg50_50 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg50_50 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg50_50
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

