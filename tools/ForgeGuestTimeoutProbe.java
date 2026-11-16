package link.e4steam.qa;

import java.io.File;
import java.io.InputStream;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketAddress;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Queue;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipFile;

/** Runs the packaged Forge guest callback and timeout paths without an external Steam peer. */
public final class ForgeGuestTimeoutProbe {
    private static final String QA = "lanminecraft.steamqa.";
    private static final String PROBE = "e4steam.guestqa.";
    private static final String MC = "net.minecraft.client.Minecraft";
    private static final String STEAM = "link.e4steam.steam.";
    private static final long DEADLINE = 120_000;
    private static final long SYNTHETIC_PEER = 77L;
    private static final long SYNTHETIC_LOBBY = 99L;

    private final Path game;
    private final Path jar;
    private final Path receipt;
    private final String mode;
    private final String digest;
    private Object client;
    private ClassLoader loader;
    private boolean ownedClient;

    private ForgeGuestTimeoutProbe() throws Exception {
        Path root = Path.of(System.getProperty(QA + "run")).toRealPath();
        require(root.getParent().getFileName().toString().equals("agent-runs")
                && root.getParent().getParent().getFileName().toString().equals("artifacts")
                && Files.isRegularFile(root.resolve("RUN.json"), LinkOption.NOFOLLOW_LINKS),
                "Expected a marked agent run");
        game = Path.of(System.getProperty(QA + "game")).toRealPath();
        Path evidence = Path.of(System.getProperty(QA + "evidence")).toRealPath();
        require(game.startsWith(root.resolve("game")) && evidence.startsWith(root.resolve("evidence")),
                "Expected an isolated game and evidence directory");
        receipt = evidence.resolve("guest-timeout-probe.json");
        require(Files.notExists(receipt, LinkOption.NOFOLLOW_LINKS), "Expected a new receipt");
        mode = System.getProperty(PROBE + "mode");
        require("stock".equals(mode) || "candidate".equals(mode), "Expected stock or candidate mode");
        String name = System.getProperty(PROBE + "jar", "");
        require(name.matches("e4steam-[A-Za-z0-9._-]+\\.jar"), "Expected an e4steam JAR basename");
        jar = game.resolve("mods").resolve(name).toRealPath();
        require(jar.getParent().equals(game.resolve("mods")), "Expected a fixture-owned JAR");
        try (var input = new DigestInputStream(Files.newInputStream(jar), MessageDigest.getInstance("SHA-256"))) {
            input.transferTo(java.io.OutputStream.nullOutputStream());
            digest = HexFormat.of().formatHex(input.getMessageDigest().digest());
        }
        require(digest.equals(System.getProperty(PROBE + "sha256")), "JAR differs from its pin");
    }

    public static void premain(String ignored, Instrumentation instrumentation) {
        try {
            var probe = new ForgeGuestTimeoutProbe();
            Thread thread = new Thread(() -> probe.run(instrumentation), "ForgeGuestTimeoutProbe");
            thread.setDaemon(true);
            thread.start();
        } catch (Exception failure) {
            failure.printStackTrace(System.err);
        }
    }

    private void run(Instrumentation instrumentation) {
        try {
            waitForTitle(instrumentation);
            verifyModule();
            try (var attempt = new Attempt()) {
                boolean loggedIn = attempt.enterGame();
                boolean fixed = "candidate".equals(mode);
                require(loggedIn == fixed, "Earlier game login and competing status connection resolved incorrectly");
                if (fixed) {
                    attempt.closeStatusProbe();
                    attempt.cleanUp(DEADLINE + 1);
                    require(!attempt.closed(attempt.login) && attempt.lobbyId() == SYNTHETIC_LOBBY,
                            "Authenticated connection was closed after the deadline");
                } else {
                    attempt.cleanUp(DEADLINE);
                    require(attempt.closed(attempt.login) && attempt.closed(attempt.status) && attempt.lobbyId() == 0L,
                            "Stock JAR did not reproduce the timed disconnect");
                }
            }
            try (var pending = new Attempt()) {
                pending.cleanUp(DEADLINE - 1);
                require(!pending.closed(pending.login), "Pending connection expired before the deadline");
                pending.cleanUp(DEADLINE);
                require(pending.closed(pending.login) && pending.lobbyId() == 0L,
                        "Pending connection no longer times out");
            }
            record("PASS", "candidate".equals(mode) ? "retained" : "closed", "");
        } catch (Throwable error) {
            try {
                record("FAIL", "unknown", error.toString());
            } catch (Exception receiptError) {
                error.addSuppressed(receiptError);
            }
            error.printStackTrace(System.err);
        } finally {
            if (ownedClient) {
                ((java.util.concurrent.Executor) client).execute(() -> {
                    try {
                        invoke(client.getClass(), client, "m_91395_");
                    } catch (ReflectiveOperationException failure) {
                        failure.printStackTrace(System.err);
                    }
                });
            }
        }
    }

    private void waitForTitle(Instrumentation instrumentation) throws Exception {
        long limit = System.nanoTime() + TimeUnit.SECONDS.toNanos(255);
        while (System.nanoTime() < limit) {
            if (client == null) {
                boolean ticking = Thread.getAllStackTraces().values().stream().flatMap(Arrays::stream)
                        .anyMatch(frame -> frame.getClassName().equals(MC) && frame.getMethodName().equals("m_91374_"));
                if (ticking) {
                    for (Class<?> loaded : instrumentation.getAllLoadedClasses()) {
                        if (!loaded.getName().equals(MC)) continue;
                        client = invoke(loaded, null, "m_91087_");
                        loader = loaded.getClassLoader();
                        break;
                    }
                }
            }
            if (client != null && onClient(() -> {
                Class<?> clazz = client.getClass();
                Path current = ((File) field(clazz, "f_91069_").get(client)).toPath().toRealPath();
                require(game.equals(current), "Minecraft has a different game directory");
                ownedClient = true;
                Object screen = field(clazz, "f_91080_").get(client);
                if (invoke(clazz, client, "m_91265_") != null) return false;
                if (screen != null && screen.getClass().getName()
                        .equals("net.minecraft.client.gui.screens.AccessibilityOnboardingScreen")) {
                    invoke(screen.getClass(), screen, "m_7379_");
                    return false;
                }
                return load("net.minecraft.client.gui.screens.TitleScreen").isInstance(screen);
            })) return;
            Thread.sleep(200);
        }
        throw new IllegalStateException("Timed out waiting for the Forge title screen");
    }

    private void verifyModule() throws Exception {
        try (var archive = new ZipFile(jar.toFile())) {
            for (String simple : new String[] { "SteamRuntime", "SteamLobbyManager", "SteamGuestJoinState",
                    "SteamConnectionBridge" }) {
                Class<?> type = load(STEAM + simple);
                require("e4steam".equals(type.getModule().getName()), "Expected the Forge e4steam module: " + simple);
                var expected = archive.getEntry(type.getName().replace('.', '/') + ".class");
                require(expected != null, "Missing pinned JAR entry: " + simple);
                try (InputStream actual = type.getResourceAsStream(simple + ".class");
                     InputStream original = archive.getInputStream(expected)) {
                    require(actual != null && Arrays.equals(actual.readAllBytes(), original.readAllBytes()),
                            "Loaded e4steam resource differs from the pinned JAR: " + simple);
                }
            }
        }
        Class<?> listener = load("net.minecraft.client.multiplayer.ClientPacketListener");
        require(Arrays.stream(listener.getDeclaredMethods())
                        .anyMatch(method -> method.getName().contains("e4steam$gameLoginCompleted")),
                "Forge Minecraft login callback is missing");
    }

    private final class Attempt implements AutoCloseable {
        private final Class<?> runtimeType = load(STEAM + "SteamRuntime");
        private final Class<?> lobbyType = load(STEAM + "SteamLobbyManager");
        private final Class<?> stateType = load(STEAM + "SteamGuestJoinState");
        private final Class<?> bridgeType = load(STEAM + "SteamConnectionBridge");
        private final Object runtime;
        private final Object lobby;
        private final Object state;
        private final Socket loginSocket = new Socket();
        private final Socket statusSocket = new Socket();
        private final Object login;
        private final Object status;

        Attempt() throws Exception {
            try {
                runtime = create(runtimeType, new Class<?>[] { load(STEAM + "SteamApi"), boolean.class }, null, false);
                // A detached runtime uses Steam's production task queue. A dormant
                // thread accepts its wakeup signal while this probe drains the queue.
                Class<?> generationType = load(STEAM + "SteamRuntime$WorkerGeneration");
                Object generation = create(generationType, new Class<?>[] { long.class }, 1L);
                field(generationType, "worker").set(generation, new Thread());
                field(runtimeType, "generation").set(runtime, generation);
                Field transport = field(runtimeType, "transport");
                // Registration checks that the worker owns a transport. All
                // traffic stays queued because this worker never runs JNI.
                transport.set(runtime, withoutNativeConstructor(transport.getType()));
                Field runtimeStatus = field(runtimeType, "status");
                for (Object value : runtimeStatus.getType().getEnumConstants()) {
                    if (((Enum<?>) value).name().equals("RUNNING")) runtimeStatus.set(runtime, value);
                }

                // Keep the real Java manager and state machine. Do not run its
                // constructor, which would create native Steamworks handles.
                lobby = withoutNativeConstructor(lobbyType);
                field(lobbyType, "runtime").set(lobby, runtime);
                field(lobbyType, "canceledJoinLobbyDeadlines").set(lobby, new HashMap<>());
                field(lobbyType, "guestLobbyId").setLong(lobby, SYNTHETIC_LOBBY);
                field(lobbyType, "guestHostSteamId").setLong(lobby, SYNTHETIC_PEER);
                field(runtimeType, "lobbyManager").set(runtime, lobby);

                state = create(stateType, new Class<?>[] { long.class }, 10L);
                field(lobbyType, "guestJoinState").set(lobby, state);
                invoke(stateType, state, "waitForConfirmation");
                require((boolean) invoke(stateType, state, "beginConnect", new Class<?>[] { long.class }, DEADLINE),
                        "Could not enter connecting state");
                login = registerBridge(loginSocket, 1);
                status = registerBridge(statusSocket, 2);
                invoke(runtimeType, runtime, "drainSteamTasks");
            } catch (Exception | Error failure) {
                try {
                    close();
                } catch (Exception closeError) {
                    failure.addSuppressed(closeError);
                }
                throw failure;
            }
        }

        private Object registerBridge(Socket socket, int id) throws Exception {
            socket.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0));
            return invoke(runtimeType, runtime, "registerClientBridge",
                    new Class<?>[] { long.class, int.class, Socket.class, AutoCloseable.class },
                    SYNTHETIC_PEER, id, socket, null);
        }

        boolean enterGame() throws Exception {
            Queue<?> queue = (Queue<?>) field(runtimeType, "steamTasks").get(runtime);
            try (Socket unknown = new Socket()) {
                unknown.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0));
                completeLogin(unknown.getLocalSocketAddress());
                require(queue.isEmpty(), "Unknown loopback connection was accepted");
            }
            completeLogin(loginSocket.getLocalSocketAddress());
            require(queue.size() == 1, "Login callback did not queue acknowledgement for the registered game socket");
            invoke(runtimeType, runtime, "drainSteamTasks");
            return (boolean) invoke(stateType, state, "isConnected");
        }

        private void completeLogin(SocketAddress address) throws Exception {
            invoke(runtimeType, runtime, "clientMinecraftJoined", new Class<?>[] { SocketAddress.class }, address);
        }

        void closeStatusProbe() throws Exception {
            invoke(bridgeType, status, "close", new Class<?>[] { boolean.class }, false);
            invoke(runtimeType, runtime, "drainSteamTasks");
            require(closed(status), "Status probe did not close");
        }

        void cleanUp(long now) throws Exception {
            try {
                invoke(lobbyType, lobby, "cleanup", new Class<?>[] { long.class }, now);
            } catch (InvocationTargetException timeout) {
                // The timeout clears the synthetic guest lobby and then tries
                // to leave it in Steamworks. No Steamworks handle exists here.
                require(timeout.getCause() instanceof NullPointerException
                                && Arrays.stream(timeout.getCause().getStackTrace())
                                .anyMatch(frame -> frame.getClassName().equals(lobbyType.getName())
                                        && frame.getMethodName().equals("leaveGuestLobby"))
                                && lobbyId() == 0L && closed(login),
                        "Unexpected failure in lobby cleanup: " + timeout.getCause());
            }
        }

        long lobbyId() throws ReflectiveOperationException {
            return field(lobbyType, "guestLobbyId").getLong(lobby);
        }

        boolean closed(Object bridge) throws ReflectiveOperationException {
            return (boolean) invoke(bridgeType, bridge, "isClosed");
        }

        @Override
        public void close() throws Exception {
            try {
                loginSocket.close();
            } finally {
                statusSocket.close();
            }
        }
    }

    private Class<?> load(String name) throws ClassNotFoundException {
        return Class.forName(name, false, loader);
    }

    private <T> T onClient(Callable<T> work) throws Exception {
        FutureTask<T> task = new FutureTask<>(work);
        ((java.util.concurrent.Executor) client).execute(task);
        return task.get(30, TimeUnit.SECONDS);
    }

    private static Field field(Class<?> type, String name) throws ReflectiveOperationException {
        Field field = type.getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }

    private static Object create(Class<?> type, Class<?>[] signature, Object... args)
            throws ReflectiveOperationException {
        Constructor<?> constructor = type.getDeclaredConstructor(signature);
        constructor.setAccessible(true);
        return constructor.newInstance(args);
    }

    private static Object withoutNativeConstructor(Class<?> type) throws ReflectiveOperationException {
        Class<?> allocator = Class.forName("sun.misc.Unsafe");
        return invoke(allocator, field(allocator, "theUnsafe").get(null), "allocateInstance",
                new Class<?>[] { Class.class }, type);
    }

    private static Object invoke(Class<?> type, Object target, String name) throws ReflectiveOperationException {
        return invoke(type, target, name, new Class<?>[0]);
    }

    private static Object invoke(Class<?> type, Object target, String name, Class<?>[] signature, Object... args)
            throws ReflectiveOperationException {
        for (Class<?> owner = type; owner != null; owner = owner.getSuperclass()) {
            Method method;
            try {
                method = owner.getDeclaredMethod(name, signature);
            } catch (NoSuchMethodException absent) {
                continue;
            }
            method.setAccessible(true);
            return method.invoke(target, args);
        }
        throw new NoSuchMethodException(type.getName() + "." + name);
    }

    private void record(String result, String loggedInSession, String failure) throws Exception {
        String message = failure.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
        Files.writeString(receipt, """
                {
                  "status": "%s",
                  "mode": "%s",
                  "sha256": "%s",
                  "deadlineMillis": %d,
                  "loggedInSessionAfterDeadline": "%s",
                  "externalSteamPeers": 0,
                  "failure": "%s"
                }
                """.formatted(result, mode, digest, DEADLINE, loggedInSession, message), StandardOpenOption.CREATE_NEW);
    }

    private static void require(boolean ok, String message) {
        if (!ok) throw new IllegalStateException(message);
    }
}
