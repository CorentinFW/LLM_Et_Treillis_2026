#!/usr/bin/env python3
"""Wrapper exécutable pour instrumenter compute_edges() sans modifier lattice2.py.

- Importe lattice2 comme module.
- Monkey-patch lattice2.compute_edges avec une version identique + logs de progression.
- Appelle lattice2.main() pour exécuter le flux normal.

Aucune dépendance externe (stdlib uniquement).
"""

from __future__ import annotations

import os
import sys
import time
from typing import List, Tuple


LOG_PERIOD_SEC = 600.0
DI_TIME_CHECK_EVERY_POW2 = 1 << 12  # 4096
DI_TIME_CHECK_MASK = DI_TIME_CHECK_EVERY_POW2 - 1

_START_TIME: float | None = None


def _format_elapsed(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _log_progress(now: float, done_work: int, total_work: int) -> None:
    start = _START_TIME
    if start is None:
        start = now
    elapsed = _format_elapsed(now - start)
    denom = total_work if total_work > 0 else 1
    pct = _clamp(100.0 * (done_work / denom), 0.0, 100.0)
    print(f"[COVER_PROGRESS] elapsed={elapsed} approx={pct:.1f}%", flush=True)


def _log_final_100(now: float) -> None:
    start = _START_TIME
    if start is None:
        start = now
    elapsed = _format_elapsed(now - start)
    print(f"[COVER_PROGRESS] elapsed={elapsed} approx=100.0%", flush=True)


def main() -> None:
    global _START_TIME

    this_dir = os.path.dirname(os.path.abspath(__file__))
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)

    import lattice2  # noqa: PLC0415

    popcount = lattice2.popcount

    _START_TIME = time.monotonic()

    def compute_edges_with_progress(concepts):
        """Copie de lattice2.compute_edges(), instrumentée avec des logs.

        Returns : list[(int, int)] — arêtes (child_idx, parent_idx).
        """
        n = len(concepts)

        # Pré-calcule approximatif du travail total (nb de candidats scannés).
        # Structure conforme à lattice2.compute_edges : intent_cards, level_index.
        if n == 0:
            now = time.monotonic()
            _log_final_100(now)
            return []

        # Pré-calcul des cardinalités d'intent
        intent_cards = [popcount(concepts[i][0]) for i in range(n)]
        max_card = max(intent_cards)

        # Index par niveau : level_index[k] = indices des concepts avec |intent| = k
        level_index = [[] for _ in range(max_card + 1)]
        for i in range(n):
            level_index[intent_cards[i]].append(i)

        level_sizes = [len(lst) for lst in level_index]
        prefix = [0] * (max_card + 1)
        running = 0
        for k in range(max_card + 1):
            running += level_sizes[k]
            prefix[k] = running

        total_work = 0
        for c_card in intent_cards:
            if c_card > 0:
                total_work += prefix[c_card - 1]

        done_work = 0
        edges = []

        next_log = (_START_TIME or time.monotonic()) + LOG_PERIOD_SEC

        for ci in range(n):
            c_intent = concepts[ci][0]
            c_card = intent_cards[ci]

            if c_card == 0:
                # Concept top (intent minimal) — aucun parent
                continue

            # Chercher les couvertures supérieures :
            # concepts dont l'intent est un sous-ensemble strict de c_intent.
            accepted_parents = []  # intents des parents acceptés

            # Parcours des niveaux de c_card-1 (le plus proche) vers 0
            for level in range(c_card - 1, -1, -1):
                level_list = level_index[level]

                for di_pos, di in enumerate(level_list):
                    d_intent = concepts[di][0]

                    # Rejet rapide : d doit être un sous-ensemble de c
                    if (d_intent & c_intent) != d_intent:
                        continue

                    # Test de domination par un parent déjà accepté
                    dominated = False
                    for p_intent in accepted_parents:
                        # d ⊂ p signifie que p est entre d et c (d au-dessus de p,
                        # p au-dessus de c), donc d n'est pas une couverture directe.
                        if (d_intent & p_intent) == d_intent and d_intent != p_intent:
                            dominated = True
                            break

                    if not dominated:
                        accepted_parents.append(d_intent)
                        edges.append((ci, di))

                    # Check horloge rare : garantit un log toutes les ~10 minutes
                    # sans appeler time.monotonic() trop souvent.
                    if (di_pos & DI_TIME_CHECK_MASK) == 0:
                        now = time.monotonic()
                        if now >= next_log:
                            # Approximation : candidats des niveaux déjà terminés +
                            # progression à l'intérieur du niveau courant.
                            approx_done = done_work + (di_pos + 1)
                            _log_progress(now, approx_done, total_work)
                            next_log = now + LOG_PERIOD_SEC

                # Tous les candidats de ce niveau ont été parcourus
                done_work += level_sizes[level]

                now = time.monotonic()
                if now >= next_log:
                    _log_progress(now, done_work, total_work)
                    next_log = now + LOG_PERIOD_SEC

        _log_final_100(time.monotonic())
        return edges

    lattice2.compute_edges = compute_edges_with_progress
    lattice2.main()


if __name__ == "__main__":
    main()
