import csv
import os
import sqlite3
import tempfile
from collections import defaultdict
from typing import List, Tuple, Dict, Set

""" Memory-efficient Formal Concept Analysis (FCA) implementation using bitmasks and SQLite for out-of-core persistence.
python3 fca.py "mushrooms_binarized/mushrooms_binarized.csv" "mushrooms.dot" """

class Context:
    """Represents a Formal Context using efficient bitmasks."""
    def __init__(self, filename: str):
        self.objects = []
        self.attributes = []
        self.matrix = [] # List of bitmasks (integers), one per object
        self._load_from_csv(filename)
        self.num_attrs = len(self.attributes)
        self.num_objs = len(self.objects)

    def _load_from_csv(self, filename: str):
        with open(filename, newline='', encoding='utf-8') as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=';,')
            except csv.Error:
                dialect = csv.excel
                dialect.delimiter = ';' if ';' in sample else ','

            reader = csv.reader(f, dialect)
            header = next(reader)
            # Remove external spaces and quotes conceptually (csv reader handles most)
            self.attributes = [col.strip() for col in header[1:]]
            
            for row in reader:
                if not row: continue
                if len(row) != len(header):
                    raise ValueError(f"Invalid row length. Expected {len(header)}, got {len(row)}")
                
                obj_name = row[0].strip()
                self.objects.append(obj_name)
                
                mask = 0
                for i, val in enumerate(row[1:]):
                    clean_val = val.strip()
                    if clean_val not in ('0', '1'):
                        raise ValueError(f"Non-binary value '{clean_val}' found in column {i+1}")
                    if clean_val == '1':
                        mask |= (1 << i)
                self.matrix.append(mask)

class FCAPipeline:
    """Memory-efficient FCA Lattice Builder and DOT Generator."""
    def __init__(self, context: Context, db_path: str = None):
        self.ctx = context
        self.db_path = db_path or tempfile.mktemp(suffix=".sqlite")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS concepts (
                intent_mask TEXT PRIMARY KEY,
                extent_mask TEXT,
                intent_size INTEGER
            )
        ''')
        self.conn.commit()

    def _mask_to_hex(self, mask: int) -> str:
        return hex(mask)

    def _hex_to_mask(self, hex_str: str) -> int:
        return int(hex_str, 16)

    def _extent_up(self, extent_mask: int) -> int:
        """A^↑: Computes intent from extent."""
        intent = (1 << self.ctx.num_attrs) - 1
        for i in range(self.ctx.num_objs):
            if (extent_mask & (1 << i)):
                intent &= self.ctx.matrix[i]
        return intent

    def _intent_down(self, intent_mask: int) -> int:
        """B^↓: Computes extent from intent."""
        extent = 0
        for i in range(self.ctx.num_objs):
            if (self.ctx.matrix[i] & intent_mask) == intent_mask:
                extent |= (1 << i)
        return extent

    def compute_lattice(self):
        """Computes all formal concepts using out-of-core persistence."""
        # Initial concepts: Bottom and Object intents
        bottom_intent = (1 << self.ctx.num_attrs) - 1
        bottom_extent = self._intent_down(bottom_intent)
        self._add_concept(bottom_intent, bottom_extent)
        
        # Incremental intersection (AddIntent variant adapted for DB)
        # We process objects in batches to bound memory
        batch_size = 100
        for i in range(0, self.ctx.num_objs, batch_size):
            end_idx = min(i + batch_size, self.ctx.num_objs)
            self._process_batch(i, end_idx)

    def _process_batch(self, start_idx: int, end_idx: int):
        # Read existing intents from DB into memory (for intersection)
        # In a strict environment, this read itself would be batched.
        self.cursor.execute('SELECT intent_mask, extent_mask FROM concepts')
        existing = [(self._hex_to_mask(i), self._hex_to_mask(e)) for i, e in self.cursor.fetchall()]
        
        new_concepts = {}
        for obj_idx in range(start_idx, end_idx):
            obj_intent = self.ctx.matrix[obj_idx]
            obj_extent = self._intent_down(obj_intent)
            new_concepts[obj_intent] = obj_extent
            
            for ext_intent, ext_extent in existing:
                inter_intent = ext_intent & obj_intent
                # Only down if we haven't seen it in our new batch
                if inter_intent not in new_concepts:
                    inter_extent = self._intent_down(inter_intent)
                    new_concepts[inter_intent] = inter_extent
        
        # Flush to DB (Deduplication handled by DB UNIQUE constraint + logic)
        for intent, extent in new_concepts.items():
            self._add_concept(intent, extent)
            
        # Also ensure top concept exists
        top_extent = (1 << self.ctx.num_objs) - 1
        top_intent = self._extent_up(top_extent)
        self._add_concept(top_intent, top_extent)

    def _add_concept(self, intent: int, extent: int):
        intent_hex = self._mask_to_hex(intent)
        extent_hex = self._mask_to_hex(extent)
        intent_size = bin(intent).count('1')
        
        self.cursor.execute('''
            INSERT INTO concepts (intent_mask, extent_mask, intent_size) 
            VALUES (?, ?, ?)
            ON CONFLICT(intent_mask) DO UPDATE SET 
            extent_mask = ?
        ''', (intent_hex, extent_hex, intent_size, extent_hex))
        self.conn.commit()

    def get_sorted_concepts(self):
        """Returns concepts ordered deterministically
           (intent_size DESC, then lexicographically by mask)."""
        self.cursor.execute('SELECT intent_mask, extent_mask, intent_size FROM concepts ORDER BY intent_size DESC, intent_mask ASC')
        return self.cursor.fetchall()

    def compute_covers(self, sorted_concepts: list) -> List[Tuple[int, int]]:
        """Computes cover relations optimized with transitive reduction."""
        edges = []
        
        # Parse masks
        parsed = []
        for idx, row in enumerate(sorted_concepts):
            parsed.append((idx, self._hex_to_mask(row[0])))
            
        # O(N^2) bitwise pruning
        for i, (c_x_id, c_x_mask) in enumerate(parsed):
            covered_attributes_mask = 0
            for j in range(i + 1, len(parsed)):
                c_y_id, c_y_mask = parsed[j]
                
                # Check subset
                if (c_y_mask & c_x_mask) == c_y_mask:
                    # Transitive reduction check
                    if (c_y_mask & covered_attributes_mask) != c_y_mask:
                        edges.append((c_x_id, c_y_id))
                        covered_attributes_mask |= c_y_mask
                        
            # Early exit: if covered_attributes_mask matches c_x_mask precisely
            # wait, c_x_mask might have attributes not in any strict subset.
        
        return edges

    def generate_dot(self, output_path: str):
        concepts = self.get_sorted_concepts()
        edges = self.compute_covers(concepts)
        
        # Build node id map
        # id corresponds to index in sorted_concepts
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("digraph G {\n")
            f.write("    rankdir=BT;\n")
            
            for node_id, (intent_hex, extent_hex, i_size) in enumerate(concepts):
                intent = self._hex_to_mask(intent_hex)
                extent = self._hex_to_mask(extent_hex)
                
                e_size = bin(extent).count('1')
                
                # Colors
                color_attrs = ""
                if e_size == 0:
                    color_attrs = "style=filled,fillcolor=lightblue,"
                elif e_size > 1:
                    color_attrs = "style=filled,fillcolor=orange,"
                    
                # Attributes list
                intent_items = [self.ctx.attributes[k] for k in range(self.ctx.num_attrs) if (intent & (1 << k))]
                intent_str = "\\n".join(self._escape(i) for i in intent_items)
                
                # Extents list
                extent_items = [self.ctx.objects[k] for k in range(self.ctx.num_objs) if (extent & (1 << k))]
                extent_str = "\\n".join(self._escape(e) for e in extent_items)
                
                label = f"{{{node_id} (I: {i_size}, E: {e_size})|{intent_str}|{extent_str}}}"
                f.write(f'    {node_id} [shape=record,{color_attrs}label="{label}"];\n')
                
            # Direct edges by source ascending then target
            edges.sort(key=lambda x: (x[0], x[1]))
            for src, tgt in edges:
                f.write(f'    {src} -> {tgt};\n')
                
            f.write("}\n")

    def _escape(self, s: str) -> str:
        s = s.replace('\\', '\\\\').replace('"', '\\"')
        return s

    def close(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python fca.py <input.csv> <output.dot>")
    else:
        input_csv = sys.argv[1]
        output_dot = sys.argv[2]
        
        ctx = Context(input_csv)
        pipeline = FCAPipeline(ctx)
        
        pipeline.compute_lattice()
        pipeline.generate_dot(output_dot)
        pipeline.close()
        
        print(f"Generated {output_dot} successfully.")
