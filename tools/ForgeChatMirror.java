import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipFile;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FieldInsnNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.objectweb.asm.tree.MethodNode;

/** Transplant the source-built chat callback into the published Forge class. */
class ForgeChatMirror {
    private static final String MIRROR = "link/e4steam/Mirror";
    private static final String UI = "link/e4steam/MinecraftUiCompat";
    private static final String MINECRAFT = "net/minecraft/";

    private static boolean chatMethod(String name) {
        return name.equals("addMessageIf") || name.equals("runChatNotification")
            || name.startsWith("lambda$addMessageIf$");
    }

    public static void main(String[] args) throws Exception {
        switch (args[0]) {
            case "merge" -> merge(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
            case "link" -> link(Path.of(args[1]), Path.of(args[2]));
            default -> throw new IllegalArgumentException(args[0]);
        }
    }

    private static void merge(Path oldClass, Path compiledClass, Path output) throws Exception {
        var stock = new ClassReader(Files.readAllBytes(oldClass));
        var compiled = new ClassReader(Files.readAllBytes(compiledClass));
        if (!MIRROR.equals(stock.getClassName()) || !MIRROR.equals(compiled.getClassName())) {
            throw new IllegalArgumentException("Only Mirror may be derived");
        }
        var sourceClass = new ClassNode(Opcodes.ASM9);
        compiled.accept(sourceClass, 0);
        List<MethodNode> methods = sourceClass.methods.stream().filter(m -> chatMethod(m.name)).toList();
        if (methods.size() != 4) throw new IllegalArgumentException("Unexpected source-built chat method inventory");
        var archive = new ClassWriter(stock, 0);
        var oldTargets = new ArrayList<String>();
        stock.accept(new ClassVisitor(Opcodes.ASM9, archive) {
            @Override public MethodVisitor visitMethod(int access, String name, String descriptor,
                    String signature, String[] exceptions) {
                if (!chatMethod(name)) return super.visitMethod(access, name, descriptor, signature, exceptions);
                oldTargets.add(name);
                return null;
            }

            @Override public void visitEnd() {
                if (oldTargets.size() != 2) throw new IllegalArgumentException("Unexpected published chat method inventory");
                for (MethodNode method : methods) method.accept(cv);
                super.visitEnd();
            }
        }, 0);
        Files.write(output, archive.toByteArray());
    }

    private static void link(Path candidate, Path forgeGame) throws Exception {
        try (var mod = new ZipFile(candidate.toFile()); var game = new ZipFile(forgeGame.toFile())) {
            var mirror = readClass(mod, MIRROR);
            var ui = readClass(mod, UI);
            require(mirror != null && ui != null, "Missing mod class");
            var required = new HashSet<String>();
            for (MethodNode method : mirror.methods) {
                if (!chatMethod(method.name)) continue;
                for (var instruction : method.instructions) {
                    if (instruction instanceof MethodInsnNode call && call.owner.equals(UI)) {
                        require(ui.methods.stream().anyMatch(m -> m.name.equals(call.name) && m.desc.equals(call.desc)),
                                "Missing mod chat entrypoint");
                        require(call.name.equals("addChatMessage"), "Unexpected chat entrypoint");
                    }
                }
                verifyDirectMembers(game, method, required);
            }
            var uiDisplay = ui.methods.stream().filter(m -> m.name.equals("addChatMessage")).findFirst().orElseThrow();
            verifyDirectMembers(game, uiDisplay, required);
            require(required.size() == 5, "Unexpected direct Minecraft chat symbol count " + required);
            for (String symbol : required.stream().sorted().toList()) System.out.println(symbol);
        }
    }

    private static void verifyDirectMembers(ZipFile game, MethodNode method, Set<String> required) throws Exception {
        for (var instruction : method.instructions) {
            if (instruction instanceof MethodInsnNode call && call.owner.startsWith(MINECRAFT)) {
                require(findMember(game, call.owner, call.name, call.desc, false), "Missing method " + call.owner + "." + call.name + call.desc);
                required.add(call.owner + "." + call.name + call.desc);
            } else if (instruction instanceof FieldInsnNode field && field.owner.startsWith(MINECRAFT)) {
                require(findMember(game, field.owner, field.name, field.desc, true), "Missing field " + field.owner + "." + field.name + field.desc);
                required.add(field.owner + "." + field.name + field.desc);
            }
        }
    }

    private static boolean findMember(ZipFile game, String owner, String name, String descriptor, boolean field) throws Exception {
        if (owner == null) return false;
        var type = readClass(game, owner);
        if (type == null) return false;
        boolean declared = field
            ? type.fields.stream().anyMatch(f -> name.equals(f.name) && descriptor.equals(f.desc))
            : type.methods.stream().anyMatch(m -> name.equals(m.name) && descriptor.equals(m.desc));
        if (declared || findMember(game, type.superName, name, descriptor, field)) return true;
        for (String implemented : type.interfaces) {
            if (findMember(game, implemented, name, descriptor, field)) return true;
        }
        return false;
    }

    private static ClassNode readClass(ZipFile jar, String name) throws Exception {
        var entry = jar.getEntry(name + ".class");
        if (entry == null) return null;
        try (InputStream input = jar.getInputStream(entry)) {
            var type = new ClassNode(Opcodes.ASM9);
            new ClassReader(input).accept(type, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
            return type;
        }
    }

    private static void require(boolean test, String message) {
        if (!test) throw new IllegalStateException(message);
    }
}
