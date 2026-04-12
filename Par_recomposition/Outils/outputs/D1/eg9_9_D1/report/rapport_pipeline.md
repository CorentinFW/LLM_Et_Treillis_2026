# Rapport pipeline - eg9_9_D1

Généré le: 2026-04-11T10:23:54+02:00

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
| claude_lattice2 | 1 | 7.54 MiB | 30.92 KiB | 0 B | 0 B |
| fca4j | 1 | 36.30 MiB | 20.33 KiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 7.36 MiB | 73.50 KiB | 0 B | 0 B |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg9_9 | fca4j | OK | 0.134 | 36.30 MiB | 20.33 KiB | 0 B | 32.00 KiB | no | yes |
| eg9_9 | claude_lattice2 | OK | 0.078 | 7.54 MiB | 30.92 KiB | 0 B | 0 B | no | yes |
| eg9_9 | gpt53_lattice | OK | 0.068 | 7.36 MiB | 73.50 KiB | 0 B | 0 B | no | yes |

## Étape normalize

| Dataset | Algo | Status | Message | DOT normalisé |
| --- | --- | --- | --- | --- |
| eg9_9 | fca4j | OK | converted to full | yes |
| eg9_9 | claude_lattice2 | OK | converted to full | yes |
| eg9_9 | gpt53_lattice | OK | converted to full | yes |

## Étape compare

| Dataset | Pair | Status | Equivalent |
| --- | --- | --- | --- |
| eg9_9 | claude_lattice2 vs fca4j | OK | true |
| eg9_9 | claude_lattice2 vs gpt53_lattice | OK | true |
| eg9_9 | fca4j vs gpt53_lattice | OK | true |

## Matrice d'équivalence

- eg9_9
  - claude_lattice2__vs__fca4j: True
  - claude_lattice2__vs__gpt53_lattice: True
  - fca4j__vs__gpt53_lattice: True

