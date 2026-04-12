# Rapport pipeline - eg9_9_D2

Généré le: 2026-04-11T14:30:03+02:00

## Résumé global

- Cas execution: 3
- Cas normalize: 3
- Paires compare: 3
- Timeouts: 0

## Ressources par algorithme

- RAM = RSS maximum observé pendant l'exécution.
- Disque max = total d'octets écrits pendant l'exécution (cumul `wchar`).
- Disque dossier pic = pic de taille totale du dossier surveillé (somme de tous les fichiers présents à cet instant, y compris les partitions).
- Disque écrit pic = pic de taille des fichiers modifiés/créés pendant l'exécution et encore présents à cet instant.
- I/O = volumes observés via /proc pendant l'exécution.

| Algo | Cas | RAM max | Disque max | Disque dossier pic | Disque écrit pic | I/O lecture max | I/O écriture max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude_lattice2 | 1 | 14.26 MiB | 0 B | 30.92 KiB | 3.22 KiB | 0 B | 0 B |
| fca4j | 1 | 40.66 MiB | 62 B | 20.33 KiB | 3.22 KiB | 0 B | 32.00 KiB |
| gpt53_lattice | 1 | 16.77 MiB | 116.46 KiB | 148.37 KiB | 110.79 KiB | 0 B | 244.00 KiB |

## Étape execution

| Dataset | Algo | Status | Elapsed(s) | RAM max | Disque max | Disque dossier pic | Disque écrit pic | I/O lecture | I/O écriture | Timeout | DOT copié |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| eg9_9 | fca4j | OK | 0.105 | 40.66 MiB | 62 B | 20.33 KiB | 3.22 KiB | 0 B | 32.00 KiB | no | yes |
| eg9_9 | claude_lattice2 | OK | 0.039 | 14.26 MiB | 0 B | 30.92 KiB | 3.22 KiB | 0 B | 0 B | no | yes |
| eg9_9 | gpt53_lattice | OK | 0.06 | 16.77 MiB | 116.46 KiB | 148.37 KiB | 110.79 KiB | 0 B | 244.00 KiB | no | yes |

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

