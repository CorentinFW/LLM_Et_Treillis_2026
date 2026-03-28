/*
 * Maven dependencies:
 * - org.apache.commons:commons-csv
 * - org.apache.commons:commons-lang3
 */

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.apache.commons.lang3.time.StopWatch;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.BitSet;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.TimeUnit;

public final class ConceptLatticeOneShot {

    private ConceptLatticeOneShot() {
    }

    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("Usage: java ConceptLatticeOneShot <input.csv> <output.dot>");
            System.exit(1);
        }

        Path inputCsv = Path.of(args[0]);
        Path outputDot = Path.of(args[1]);

        try {
            FormalContext context = parseFormalContext(inputCsv);

            ThreadMXBean mxBean = ManagementFactory.getThreadMXBean();
            boolean cpuSupported = mxBean.isCurrentThreadCpuTimeSupported();
            if (cpuSupported && !mxBean.isThreadCpuTimeEnabled()) {
                try {
                    mxBean.setThreadCpuTimeEnabled(true);
                } catch (UnsupportedOperationException ignored) {
                    cpuSupported = false;
                }
            }

            long cpuStartNs = cpuSupported ? mxBean.getCurrentThreadCpuTime() : -1L;
            StopWatch stopWatch = StopWatch.createStarted();

            List<Concept> concepts = computeConceptLatticeNextClosure(context);
            List<Edge> coverEdges = computeHasseEdges(concepts);

            stopWatch.stop();
            long cpuEndNs = cpuSupported ? mxBean.getCurrentThreadCpuTime() : -1L;

            writeDot(outputDot, concepts, coverEdges, context);

            long wallMs = stopWatch.getTime(TimeUnit.MILLISECONDS);
            long cpuMs = cpuSupported ? (cpuEndNs - cpuStartNs) / 1_000_000L : -1L;

            System.out.printf(Locale.ROOT, "Wall-clock time (ms): %d%n", wallMs);
            if (cpuSupported) {
                System.out.printf(Locale.ROOT, "CPU time (ms): %d%n", cpuMs);
            } else {
                System.out.println("CPU time (ms): unavailable");
            }
        } catch (IllegalArgumentException e) {
            System.err.println("Input format error: " + e.getMessage());
            System.exit(2);
        } catch (IOException e) {
            System.err.println("I/O error: " + e.getMessage());
            System.exit(3);
        } catch (Exception e) {
            System.err.println("Unexpected error: " + e.getMessage());
            System.exit(4);
        }
    }

    private static FormalContext parseFormalContext(Path inputCsv) throws IOException {
        if (!Files.isReadable(inputCsv)) {
            throw new IllegalArgumentException("Input CSV is not readable: " + inputCsv);
        }

        CSVFormat format = CSVFormat.DEFAULT.builder()
                .setDelimiter(';')
                .setTrim(true)
                .setIgnoreSurroundingSpaces(true)
                .build();

        try (BufferedReader reader = Files.newBufferedReader(inputCsv, StandardCharsets.UTF_8);
             CSVParser parser = new CSVParser(reader, format)) {

            Iterator<CSVRecord> it = parser.iterator();
            if (!it.hasNext()) {
                throw new IllegalArgumentException("CSV file is empty.");
            }

            CSVRecord header = it.next();
            int columnCount = header.size();
            if (columnCount < 2) {
                throw new IllegalArgumentException("Header must contain an empty first cell and at least one attribute.");
            }

            String firstCell = valueOrEmpty(header.get(0));
            if (!firstCell.isEmpty()) {
                throw new IllegalArgumentException("First header cell must be empty.");
            }

            List<String> attributes = new ArrayList<>();
            Set<String> attributeNames = new HashSet<>();
            for (int j = 1; j < columnCount; j++) {
                String name = valueOrEmpty(header.get(j));
                if (name.isEmpty()) {
                    throw new IllegalArgumentException("Attribute name is empty at column " + (j + 1) + ".");
                }
                if (!attributeNames.add(name)) {
                    throw new IllegalArgumentException("Duplicate attribute name: " + name);
                }
                attributes.add(name);
            }

            List<String> objects = new ArrayList<>();
            List<BitSet> incidence = new ArrayList<>();
            Set<String> objectNames = new HashSet<>();

            long rowNumber = 1;
            while (it.hasNext()) {
                CSVRecord row = it.next();
                rowNumber++;

                if (row.size() != columnCount) {
                    throw new IllegalArgumentException("Invalid column count at row " + rowNumber
                            + ": expected " + columnCount + " but got " + row.size() + ".");
                }

                String objectName = valueOrEmpty(row.get(0));
                if (objectName.isEmpty()) {
                    throw new IllegalArgumentException("Object name is empty at row " + rowNumber + ".");
                }
                if (!objectNames.add(objectName)) {
                    throw new IllegalArgumentException("Duplicate object name: " + objectName);
                }

                BitSet attrs = new BitSet(attributes.size());
                for (int j = 1; j < columnCount; j++) {
                    String cell = valueOrEmpty(row.get(j));
                    if ("1".equals(cell)) {
                        attrs.set(j - 1);
                    } else if (!"0".equals(cell)) {
                        throw new IllegalArgumentException("Invalid binary value at row " + rowNumber
                                + ", column " + (j + 1) + ": " + cell + " (expected 0 or 1)");
                    }
                }

                objects.add(objectName);
                incidence.add(attrs);
            }

            if (objects.isEmpty()) {
                throw new IllegalArgumentException("CSV contains no objects.");
            }

            return new FormalContext(objects, attributes, incidence);
        }
    }

    private static String valueOrEmpty(String s) {
        return s == null ? "" : s.trim();
    }

    // Next Closure enumerates all closed intents once; complexity is output-sensitive and exponential in worst-case.
    private static List<Concept> computeConceptLatticeNextClosure(FormalContext context) {
        List<Concept> concepts = new ArrayList<>();
        BitSet current = closure(context, new BitSet(context.attributeCount));

        int id = 0;
        while (current != null) {
            BitSet intent = cloneBitSet(current);
            BitSet extent = extentFromIntent(context, intent);
            concepts.add(new Concept(id++, extent, intent));
            current = nextClosure(context, current);
        }

        return concepts;
    }

    private static BitSet nextClosure(FormalContext context, BitSet current) {
        int m = context.attributeCount;
        for (int i = m - 1; i >= 0; i--) {
            if (!current.get(i)) {
                BitSet candidate = prefixWithAddedAttribute(current, i);
                BitSet closed = closure(context, candidate);
                if (closed.get(i) && samePrefix(current, closed, i)) {
                    return closed;
                }
            }
        }
        return null;
    }

    private static BitSet prefixWithAddedAttribute(BitSet source, int i) {
        BitSet result = new BitSet();
        for (int j = source.nextSetBit(0); j >= 0 && j < i; j = source.nextSetBit(j + 1)) {
            result.set(j);
        }
        result.set(i);
        return result;
    }

    private static boolean samePrefix(BitSet a, BitSet b, int limitExclusive) {
        for (int j = 0; j < limitExclusive; j++) {
            if (a.get(j) != b.get(j)) {
                return false;
            }
        }
        return true;
    }

    private static BitSet closure(FormalContext context, BitSet intent) {
        return intentFromExtent(context, extentFromIntent(context, intent));
    }

    private static BitSet extentFromIntent(FormalContext context, BitSet intent) {
        BitSet extent = new BitSet(context.objectCount);
        extent.set(0, context.objectCount);

        for (int obj = extent.nextSetBit(0); obj >= 0; obj = extent.nextSetBit(obj + 1)) {
            if (!isSubset(intent, context.objectAttributes.get(obj))) {
                extent.clear(obj);
            }
        }
        return extent;
    }

    private static BitSet intentFromExtent(FormalContext context, BitSet extent) {
        BitSet intent = new BitSet(context.attributeCount);
        intent.set(0, context.attributeCount);

        for (int obj = extent.nextSetBit(0); obj >= 0; obj = extent.nextSetBit(obj + 1)) {
            intent.and(context.objectAttributes.get(obj));
        }
        return intent;
    }

    private static boolean isSubset(BitSet subset, BitSet superset) {
        BitSet tmp = cloneBitSet(subset);
        tmp.andNot(superset);
        return tmp.isEmpty();
    }

    // Cover computation: keep only immediate strict intent inclusions (transitive reduction in concept order).
    private static List<Edge> computeHasseEdges(List<Concept> concepts) {
        List<Edge> edges = new ArrayList<>();
        int n = concepts.size();

        for (int from = 0; from < n; from++) {
            BitSet fromIntent = concepts.get(from).intent;
            for (int to = 0; to < n; to++) {
                if (from == to) {
                    continue;
                }
                BitSet toIntent = concepts.get(to).intent;
                if (!isProperSubset(toIntent, fromIntent)) {
                    continue;
                }

                boolean covered = true;
                for (int mid = 0; mid < n; mid++) {
                    if (mid == from || mid == to) {
                        continue;
                    }
                    BitSet midIntent = concepts.get(mid).intent;
                    if (isProperSubset(toIntent, midIntent) && isProperSubset(midIntent, fromIntent)) {
                        covered = false;
                        break;
                    }
                }

                if (covered) {
                    edges.add(new Edge(from, to));
                }
            }
        }

        return edges;
    }

    private static boolean isProperSubset(BitSet a, BitSet b) {
        return !a.equals(b) && isSubset(a, b);
    }

    private static void writeDot(Path outputDot,
                                 List<Concept> concepts,
                                 List<Edge> edges,
                                 FormalContext context) throws IOException {
        Path parent = outputDot.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }

        try (BufferedWriter writer = Files.newBufferedWriter(outputDot, StandardCharsets.UTF_8)) {
            writer.write("digraph G {\n");
            writer.write("    rankdir=BT;\n");

            for (Concept concept : concepts) {
                String label = buildRecordLabel(concept, context);
                writer.write(String.format(Locale.ROOT,
                        "    %d [shape=record,style=filled,label=\"%s\"];%n",
                        concept.id,
                        label));
            }

            for (Edge edge : edges) {
                writer.write(String.format(Locale.ROOT, "    %d -> %d%n", edge.fromId, edge.toId));
            }

            writer.write("}\n");
        }
    }

    private static String buildRecordLabel(Concept concept, FormalContext context) {
        String intentText = joinBitSetItems(concept.intent, context.attributes);
        String extentText = joinBitSetItems(concept.extent, context.objects);

        return "{" + concept.id
                + " (E: " + concept.extent.cardinality()
                + ", I: " + concept.intent.cardinality() + ")"
                + "|" + intentText
                + "|" + extentText
                + "}";
    }

    private static String joinBitSetItems(BitSet indices, List<String> values) {
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (int i = indices.nextSetBit(0); i >= 0; i = indices.nextSetBit(i + 1)) {
            if (!first) {
                sb.append("\\n");
            }
            sb.append(escapeDotRecordText(values.get(i)));
            first = false;
        }
        return sb.toString();
    }

    private static String escapeDotRecordText(String text) {
        StringBuilder sb = new StringBuilder(text.length() + 8);
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            switch (c) {
                case '\\' -> sb.append("\\\\");
                case '"' -> sb.append("\\\"");
                case '{' -> sb.append("\\{");
                case '}' -> sb.append("\\}");
                case '|' -> sb.append("\\|");
                case '<' -> sb.append("\\<");
                case '>' -> sb.append("\\>");
                case '\n', '\r' -> sb.append("\\n");
                default -> sb.append(c);
            }
        }
        return sb.toString();
    }

    private static BitSet cloneBitSet(BitSet bitSet) {
        return (BitSet) bitSet.clone();
    }

    private static final class FormalContext {
        final List<String> objects;
        final List<String> attributes;
        final List<BitSet> objectAttributes;
        final int objectCount;
        final int attributeCount;

        FormalContext(List<String> objects, List<String> attributes, List<BitSet> objectAttributes) {
            this.objects = List.copyOf(objects);
            this.attributes = List.copyOf(attributes);
            this.objectAttributes = objectAttributes.stream().map(ConceptLatticeOneShot::cloneBitSet).toList();
            this.objectCount = objects.size();
            this.attributeCount = attributes.size();
        }
    }

    private static final class Concept {
        final int id;
        final BitSet extent;
        final BitSet intent;

        Concept(int id, BitSet extent, BitSet intent) {
            this.id = id;
            this.extent = cloneBitSet(extent);
            this.intent = cloneBitSet(intent);
        }
    }

    private static final class Edge {
        final int fromId;
        final int toId;

        Edge(int fromId, int toId) {
            this.fromId = fromId;
            this.toId = toId;
        }
    }
}
