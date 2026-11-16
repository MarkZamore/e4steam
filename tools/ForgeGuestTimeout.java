import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipFile;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.MethodNode;

/** Transplants only the reviewed guest lifecycle methods into the stock Forge classes. */
class ForgeGuestTimeout {
    private static final String PACKAGE = "link/e4steam/steam/";
    private static final String BRIDGE = "L" + PACKAGE + "SteamConnectionBridge;";
    private static final String JOINED = "clientMinecraftJoined(" + BRIDGE + ")V";
    private static final String CLOSED_BEFORE = "clientBridgeClosed(" + BRIDGE + "Z)V";
    private static final String CLOSED_AFTER = "clientBridgeClosed(" + BRIDGE + ")V";
    private static final String UNREGISTER = "unregister(" + BRIDGE + ")V";
    private static final String LAMBDA_BEFORE = "lambda$unregister$17(" + BRIDGE + "Z)Ljava/lang/Object;";
    private static final String LAMBDA_AFTER = "lambda$unregister$17(" + BRIDGE + ")Ljava/lang/Object;";

    public static void main(String[] args) throws IOException {
        try (var original = new ZipFile(args[0])) {
            Path compiled = Path.of(args[1]);
            Path out = Path.of(args[2]);
            Files.createDirectories(out.resolve(PACKAGE));
            transplant(original, compiled, out, "SteamLobbyManager",
                       Map.of(JOINED, JOINED, CLOSED_BEFORE, CLOSED_AFTER));
            transplant(original, compiled, out, "SteamRuntime",
                       Map.of(UNREGISTER, UNREGISTER, LAMBDA_BEFORE, LAMBDA_AFTER));
            String state = PACKAGE + "SteamGuestJoinState.class";
            byte[] stateBody = Files.readAllBytes(compiled.resolve(state));
            require(read(new ClassReader(stateBody)).version == Opcodes.V17, "Guest state needs Java 17");
            Files.write(out.resolve(state), stateBody);
        }
    }

    private static void transplant(ZipFile original, Path compiled, Path out, String name,
                                   Map<String, String> methods) throws IOException {
        String entry = PACKAGE + name + ".class";
        ClassReader stockReader;
        try (var input = original.getInputStream(original.getEntry(entry))) {
            stockReader = new ClassReader(input.readAllBytes());
        }
        ClassNode stock = read(stockReader);
        ClassNode source = read(new ClassReader(Files.readAllBytes(compiled.resolve(entry))));
        require(stock.name.equals(source.name) && stock.version == Opcodes.V17 && source.version == stock.version,
                "Class identity or target differs: " + name);
        List<MethodNode> untouched = List.copyOf(stock.methods);
        for (var pair : methods.entrySet()) {
            MethodNode from = method(stock, pair.getKey());
            MethodNode into = method(source, pair.getValue());
            require(from.access == into.access, "Method access changed: " + pair.getKey());
            stock.methods.set(stock.methods.indexOf(from), into);
        }
        var writer = new ClassWriter(stockReader, 0);
        stock.accept(writer);
        byte[] candidate = writer.toByteArray();
        ClassNode check = read(new ClassReader(candidate));
        require(check.methods.size() == untouched.size(), "Method count changed: " + name);
        for (MethodNode before : untouched) {
            String signature = key(before);
            MethodNode expected = methods.containsKey(signature) ? method(source, methods.get(signature)) : before;
            require(Arrays.equals(methodBytes(expected), methodBytes(method(check, key(expected)))),
                    "Unexpected method contents: " + name + "." + signature);
        }
        Files.write(out.resolve(entry), candidate);
    }

    private static ClassNode read(ClassReader reader) {
        var node = new ClassNode(Opcodes.ASM9);
        reader.accept(node, 0);
        return node;
    }

    private static MethodNode method(ClassNode node, String key) {
        var matches = node.methods.stream().filter(member -> key(member).equals(key)).toList();
        require(matches.size() == 1, "Expected one method " + node.name + "." + key);
        return matches.get(0);
    }

    private static String key(MethodNode method) {
        return method.name + method.desc;
    }

    private static byte[] methodBytes(MethodNode method) {
        var writer = new ClassWriter(0);
        writer.visit(Opcodes.V17, Opcodes.ACC_PUBLIC, "MethodBody", null, "java/lang/Object", null);
        method.accept(writer);
        return writer.toByteArray();
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
}
