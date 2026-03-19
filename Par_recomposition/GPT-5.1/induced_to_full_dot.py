#!/usr/bin/env python3
# python3 <chemin_vers_ce_script>/induced_to_full_dot.py <chemin_input_reduced.dot> <chemin_output_full.dot>

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Iterable


@dataclass
class Node:
    node_id: str
    # Attributes as parsed from DOT (without the label), in original order
    attrs_order: List[str] = field(default_factory=list)
    attrs: Dict[str, str] = field(default_factory=dict)
    # Label parts (reduced)
    header: str | None = None
    reduced_intent: List[str] = field(default_factory=list)
    reduced_extent: List[str] = field(default_factory=list)
    # Reconstructed full sets
    full_intent: Set[str] = field(default_factory=set)
    full_extent: Set[str] = field(default_factory=set)


def parse_attributes(attr_str: str) -> Tuple[Dict[str, str], List[str]]:
    """Parse the content between [...] into a dict and an ordered key list.

    Very small, robust parser for key=value pairs separated by commas,
    with values optionally quoted by double quotes. It assumes no nested
    quotes and no commas inside quoted strings (satisfied for FCA4J-style DOT).
    """
    attrs: Dict[str, str] = {}
    order: List[str] = []

    s = attr_str.strip().strip("[]")
    if not s:
        return attrs, order

    parts: List[str] = []
    current: List[str] = []
    in_quotes = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"':
            in_quotes = not in_quotes
            current.append(ch)
        elif ch == ',' and not in_quotes:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        part = "".join(current).strip()
        if part:
            parts.append(part)

    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes from value if present
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            attrs[key] = value
            order.append(key)
        else:
            # Attribute without explicit value (rare in our setting)
            key = part.strip()
            attrs[key] = ""
            order.append(key)

    return attrs, order


def parse_record_label(label: str) -> Tuple[str, List[str], List[str]]:
    """Parse a FCA4J-style record label.

    Expected general form:
        {HEADER|INTENT_PART|EXTENT_PART}

    where INTENT_PART and EXTENT_PART are lists of items separated by `\n`.
    Empty fields are allowed (e.g. `||` or `|...|`).
    Returns (header, intent_list, extent_list).
    """
    s = label.strip()
    if s.startswith('{') and s.endswith('}'):
        s = s[1:-1]

    parts = s.split('|')
    if len(parts) != 3:
        raise ValueError(f"Label does not have 3 record fields: {label!r}")

    header = parts[0].strip()
    raw_intent = parts[1]
    raw_extent = parts[2]

    def split_items(part: str) -> List[str]:
        # In DOT file, line breaks in record fields are encoded as "\\n"
        if not part:
            return []
        tokens = part.split("\\n")
        items: List[str] = []
        for t in tokens:
            item = t.strip()
            if item:
                items.append(item)
        return items

    intent_items = split_items(raw_intent)
    extent_items = split_items(raw_extent)
    return header, intent_items, extent_items


def parse_dot_file(path: str) -> Tuple[Dict[str, Node], List[Tuple[str, str]]]:
    """Parse a reduced-labeled lattice DOT file.

    Returns:
        nodes: mapping id -> Node (with reduced_intent/extent)
        edges: list of (src, dst) following the DOT orientation (u -> v)
    """
    nodes: Dict[str, Node] = {}
    edges: List[Tuple[str, str]] = []

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('//'):
                continue
            if stripped.startswith('digraph') or stripped.startswith('rankdir') or stripped == '}':
                # Handled at write time; we don't need to store these lines
                continue

            # Edge definition
            if '->' in stripped:
                # Example:  1 -> 0
                left, _sep, _rest = stripped.partition('->')
                src = left.strip()
                # Right side may have attributes or semicolon
                right = _rest.strip()
                # Cut off everything after target id (space, '[', ';', etc.)
                dst_chars: List[str] = []
                for ch in right:
                    if ch.isalnum() or ch in ('_', '-'):
                        dst_chars.append(ch)
                    else:
                        break
                dst = "".join(dst_chars)
                if src and dst:
                    edges.append((src, dst))
                continue

            # Node definition (we assume any non-edge line with '[' is a node)
            if '[' in stripped and ']' in stripped:
                before, _lbr, rest = stripped.partition('[')
                node_id = before.strip()
                # Extract attribute block
                attr_block, _rbr, _after = rest.partition(']')
                attrs, order = parse_attributes(attr_block)

                label_value = attrs.get('label')
                header = None
                reduced_intent: List[str] = []
                reduced_extent: List[str] = []
                if label_value is not None:
                    header, reduced_intent, reduced_extent = parse_record_label(label_value)

                # Remove label from attrs: we will rebuild it later
                if 'label' in attrs:
                    del attrs['label']
                    order = [k for k in order if k != 'label']

                node = Node(
                    node_id=node_id,
                    attrs_order=order,
                    attrs=attrs,
                    header=header,
                    reduced_intent=reduced_intent,
                    reduced_extent=reduced_extent,
                )
                nodes[node_id] = node

    if not nodes:
        raise ValueError(f"No nodes parsed from DOT file: {path}")

    return nodes, edges


def build_dag(nodes: Dict[str, Node], edges: List[Tuple[str, str]]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Build successor and predecessor lists for the DAG.

    succ[u] contains v if there is an edge u -> v.
    pred[v] contains u if there is an edge u -> v.
    """
    succ: Dict[str, List[str]] = {nid: [] for nid in nodes}
    pred: Dict[str, List[str]] = {nid: [] for nid in nodes}

    for u, v in edges:
        if u not in nodes or v not in nodes:
            raise ValueError(f"Edge references unknown node: {u} -> {v}")
        succ[u].append(v)
        pred[v].append(u)

    return succ, pred


def topological_sort(nodes: Dict[str, Node], succ: Dict[str, List[str]]) -> List[str]:
    """Compute a topological order of the DAG using Kahn's algorithm.

    Raises ValueError if a cycle is detected.
    """
    # Compute in-degrees
    indegree: Dict[str, int] = {nid: 0 for nid in nodes}
    for u, vs in succ.items():
        for v in vs:
            indegree[v] += 1

    # Start with nodes of indegree 0, sorted for determinism
    zero_indegree: List[str] = sorted([nid for nid, d in indegree.items() if d == 0])
    order: List[str] = []

    while zero_indegree:
        n = zero_indegree.pop(0)
        order.append(n)
        for v in succ[n]:
            indegree[v] -= 1
            if indegree[v] == 0:
                zero_indegree.append(v)
        zero_indegree.sort()  # keep deterministic

    if len(order) != len(nodes):
        raise ValueError("Cycle detected in graph: not a DAG; cannot reconstruct lattice.")

    return order


def reconstruct_full_intents(nodes: Dict[str, Node], succ: Dict[str, List[str]], topo_order: List[str]) -> None:
    """Reconstruct full intents from reduced intents.

    For each node n:
        full_intent[n] = reduced_intent[n] ∪ ⋃_{s in succ[n]} full_intent[s]

    We process nodes in reverse topological order so that all successors
    are processed before a node.
    """
    for nid in reversed(topo_order):
        node = nodes[nid]
        full: Set[str] = set(node.reduced_intent)
        for s in succ[nid]:
            full.update(nodes[s].full_intent)
        node.full_intent = full


def reconstruct_full_extents(nodes: Dict[str, Node], pred: Dict[str, List[str]], topo_order: List[str]) -> None:
    """Reconstruct full extents from reduced extents.

    For each node n:
        full_extent[n] = reduced_extent[n] ∪ ⋃_{p in pred[n]} full_extent[p]

    We process nodes in topological order so that all predecessors
    are processed before a node.
    """
    for nid in topo_order:
        node = nodes[nid]
        full: Set[str] = set(node.reduced_extent)
        for p in pred[nid]:
            full.update(nodes[p].full_extent)
        node.full_extent = full


def validate_lattice(nodes: Dict[str, Node], edges: Iterable[Tuple[str, str]]) -> None:
    """Check that intents/extents are monotone along edges of the lattice.

    For each edge u -> v we expect:
        full_intent[v] ⊆ full_intent[u]
        full_extent[u] ⊆ full_extent[v]

    Raises ValueError if any violation is found.
    """
    for u, v in edges:
        nu = nodes[u]
        nv = nodes[v]
        if not nv.full_intent.issubset(nu.full_intent):
            raise ValueError(
                f"Intent monotonicity violated on edge {u} -> {v}: "
                f"intent({v}) not subset of intent({u})"
            )
        if not nu.full_extent.issubset(nv.full_extent):
            raise ValueError(
                f"Extent monotonicity violated on edge {u} -> {v}: "
                f"extent({u}) not subset of extent({v})"
            )


def escape_label_text(text: str) -> str:
    """Escape characters that are special inside a DOT quoted label."""
    # Minimal escaping for our setting: backslash and double quote
    return text.replace('\\', '\\\\').replace('"', '\\"')


def build_full_label(node: Node) -> str:
    """Build the full DOT record label for a node from its full sets.

    Format:
        {ID (I: X, E: Y)|a1\na2\n...|o1\no2\n...}

    Attribute and object names are sorted lexicographically to get
    a deterministic order and to avoid duplicates.
    """
    intent_items = sorted(node.full_intent)
    extent_items = sorted(node.full_extent)

    intent_part = "\\n".join(intent_items) if intent_items else ""
    extent_part = "\\n".join(extent_items) if extent_items else ""

    header = f"{node.node_id} (I: {len(intent_items)}, E: {len(extent_items)})"
    label_text = f"{{{header}|{intent_part}|{extent_part}}}"
    return escape_label_text(label_text)


def write_full_dot(path: str, nodes: Dict[str, Node], edges: List[Tuple[str, str]]) -> None:
    """Write a DOT file with reconstructed full labels.

    We regenerate a simple, deterministic DOT:
        digraph G {
            rankdir=BT;
            <nodes>
            <edges>
        }
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write("digraph G {\n")
        f.write("\trankdir=BT;\n")

        # Preserve a deterministic node order: sort by numeric id if possible,
        # else lexicographically.
        def sort_key(nid: str):
            try:
                return (0, int(nid))
            except ValueError:
                return (1, nid)

        for nid in sorted(nodes.keys(), key=sort_key):
            node = nodes[nid]
            label_value = build_full_label(node)

            # Rebuild attribute list, preserving original order for non-label attrs
            parts: List[str] = []
            for key in node.attrs_order:
                value = node.attrs.get(key, "")
                if key == 'label':
                    # We removed it at parse time, but keep branch for safety
                    continue
                if value == "":
                    parts.append(key)
                else:
                    # Re-quote value
                    parts.append(f"{key}=\"{escape_label_text(value)}\"")

            # Finally add the new label
            parts.append(f"label=\"{label_value}\"")

            attrs_str = ",".join(parts)
            line = f"\t{nid} [{attrs_str}];\n"
            f.write(line)

        # Edges in the same order as parsed
        for u, v in edges:
            f.write(f"\t{u} -> {v}\n")

        f.write("}\n")


def convert_induced_dot_to_full_dot(input_path: str, output_path: str) -> None:
    """High-level conversion pipeline from reduced to full DOT lattice."""
    nodes, edges = parse_dot_file(input_path)
    succ, pred = build_dag(nodes, edges)
    topo = topological_sort(nodes, succ)
    reconstruct_full_intents(nodes, succ, topo)
    reconstruct_full_extents(nodes, pred, topo)
    validate_lattice(nodes, edges)
    write_full_dot(output_path, nodes, edges)


def main(argv: List[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 2:
        print("Usage: python induced_to_full_dot.py input.dot output.dot", file=sys.stderr)
        raise SystemExit(1)

    input_path, output_path = argv
    convert_induced_dot_to_full_dot(input_path, output_path)


if __name__ == "__main__":
    main()
