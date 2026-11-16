import io.netty.buffer.ByteBuf;
import io.netty.channel.ChannelFutureListener;
import io.netty.channel.ChannelHandler;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.ChannelPromise;
import io.netty.channel.embedded.EmbeddedChannel;
import io.netty.util.AttributeKey;
import io.netty.util.concurrent.GenericFutureListener;
import link.e4steam.retro.forge.Forge112LoginHandshake;
import org.apache.commons.io.IOUtils;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Runs Forge 2859's actual patched NetworkManager writer and vanilla 1.12.2 packet
 * encoder without a client, world, sockets, Steam account or system configuration.
 */
public final class Forge112LoginOrderProbe {
    public static void main(String[] args) throws Exception {
        try (ForgeRuntime runtime = new ForgeRuntime(args)) {
            reproduceEarlyPlay(runtime);
            checkOrderedLogin(runtime);
            checkFailedWrite(runtime);
            checkDisconnectedBeforeHandshake(runtime);
        }
        System.out.println("PASS 4 cases: reproduced PLAY/null, LOGIN id 2 before PLAY, failed write, closed channel");
    }

    private static void reproduceEarlyPlay(ForgeRuntime runtime) throws Exception {
        try (Connection connection = new Connection(runtime)) {
            Runnable queuedLogin = connection.queueLogin(null);
            // Forge's NetworkDispatcher.serverInitiateHandshake makes this direct call.
            connection.enterPlay();
            queuedLogin.run();
            require(connection.channel.readOutbound() == null, "LoginSuccess emitted a PLAY packet");
            require(hasCause(connection.failure, "Can't serialize unregistered packet"),
                    "Wrong failure of the original writer: " + connection.failure);
        }
    }

    private static void checkOrderedLogin(ForgeRuntime runtime) throws Exception {
        try (Connection connection = new Connection(runtime)) {
            ChannelPromise loginWrite = connection.channel.newPromise();
            Queue<Runnable> serverTasks = new ArrayDeque<>();
            AtomicInteger starts = new AtomicInteger();
            Forge112LoginHandshake.afterLoginSuccess(loginWrite, serverTasks::add, () -> {
                starts.incrementAndGet();
                connection.enterPlay();
            });
            require(serverTasks.isEmpty(), "Forge handshake scheduled while login write is pending");

            connection.queueLogin(loginWrite).run();
            connection.channel.runPendingTasks();
            require(connection.failure == null && loginWrite.isSuccess(), "LoginSuccess write failed");
            require(connection.currentState() == runtime.login, "Protocol changed on the Netty write thread");
            ByteBuf packet = connection.channel.readOutbound();
            require(packet != null, "Missing encoded LoginSuccess");
            try {
                require(packet.readUnsignedByte() == 2, "Incorrect LoginSuccess packet ID");
                require(packet.isReadable(), "Missing LoginSuccess payload");
            } finally {
                packet.release();
            }
            require(serverTasks.size() == 1, "Expected one Minecraft server task");
            serverTasks.remove().run();
            require(connection.currentState() == runtime.play && starts.get() == 1,
                    "Forge handshake did not advance to PLAY once");
        }
    }

    private static void checkFailedWrite(ForgeRuntime runtime) throws Exception {
        try (Connection connection = new Connection(runtime)) {
            ChannelPromise write = connection.channel.newPromise();
            Queue<Runnable> serverTasks = new ArrayDeque<>();
            Forge112LoginHandshake.afterLoginSuccess(write, serverTasks::add, connection::enterPlay);
            write.setFailure(new IOException("Test login write failure"));
            connection.channel.runPendingTasks();
            require(serverTasks.isEmpty() && connection.currentState() == runtime.login,
                    "Failed login write started Forge handshake");
        }
    }

    private static void checkDisconnectedBeforeHandshake(ForgeRuntime runtime) throws Exception {
        try (Connection connection = new Connection(runtime)) {
            ChannelPromise write = connection.channel.newPromise();
            Queue<Runnable> serverTasks = new ArrayDeque<>();
            Forge112LoginHandshake.afterLoginSuccess(write, serverTasks::add, connection::enterPlay);
            write.setSuccess();
            connection.channel.runPendingTasks();
            require(serverTasks.size() == 1, "Successful write did not schedule Forge handshake");
            connection.channel.close().syncUninterruptibly();
            serverTasks.remove().run();
            require(connection.currentState() == runtime.login, "Closed channel entered PLAY");
        }
    }

    private static boolean hasCause(Throwable exception, String message) {
        for (Throwable current = exception; current != null; current = current.getCause()) {
            if (message.equals(current.getMessage())) return true;
        }
        return false;
    }

    private static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    private static final class Connection implements AutoCloseable {
        private final ForgeRuntime runtime;
        private final EmbeddedChannel channel;
        private final Object manager;
        private Throwable failure;

        Connection(ForgeRuntime runtime) throws Exception {
            this.runtime = runtime;
            manager = runtime.managerConstructor.newInstance(runtime.serverbound);
            ChannelHandler encoder = (ChannelHandler) runtime.encoderConstructor.newInstance(runtime.clientbound);
            channel = new EmbeddedChannel(encoder, new ChannelInboundHandlerAdapter() {
                @Override
                public void exceptionCaught(ChannelHandlerContext context, Throwable cause) {
                    failure = cause;
                }
            });
            runtime.networkChannel.set(manager, channel);
            runtime.setState.invoke(manager, runtime.login);
        }

        Runnable queueLogin(ChannelPromise result) throws Exception {
            Object profile = runtime.profileConstructor.newInstance(new UUID(0, 1), "ForgeQa");
            Object packet = runtime.loginPacketConstructor.newInstance(profile);
            GenericFutureListener<?>[] listeners = null;
            if (result != null) {
                ChannelFutureListener writeCompleted = future -> {
                    if (future.isSuccess()) result.setSuccess();
                    else result.setFailure(future.cause());
                };
                listeners = new GenericFutureListener<?>[] { writeCompleted };
            }
            // EmbeddedEventLoop.inEventLoop always returns true. Construct the real
            // asynchronous writer explicitly to hold it at the exact race boundary.
            return (Runnable) runtime.writeConstructor.newInstance(manager, runtime.login, currentState(), packet, listeners);
        }

        Object currentState() {
            return channel.attr(runtime.stateKey).get();
        }

        void enterPlay() {
            try {
                runtime.setState.invoke(manager, runtime.play);
            } catch (ReflectiveOperationException e) {
                throw new AssertionError("Cannot perform native state change", e);
            }
        }

        @Override
        public void close() {
            channel.finishAndReleaseAll();
        }
    }

    private static final class ForgeRuntime extends URLClassLoader {
        private final Object patches;
        private final Method applyPatch;
        private final Constructor<?> managerConstructor;
        private final Constructor<?> encoderConstructor;
        private final Constructor<?> writeConstructor;
        private final Constructor<?> profileConstructor;
        private final Constructor<?> loginPacketConstructor;
        private final Field networkChannel;
        private final Method setState;
        private final AttributeKey<Object> stateKey;
        private final Object login;
        private final Object play;
        private final Object serverbound;
        private final Object clientbound;

        @SuppressWarnings("unchecked")
        ForgeRuntime(String[] paths) throws Exception {
            super(new URL[] { Paths.get(paths[0]).toUri().toURL(), Paths.get(paths[1]).toUri().toURL() },
                    Forge112LoginOrderProbe.class.getClassLoader());
            Class<?> patchManager = loadClass("net.minecraftforge.fml.common.patcher.ClassPatchManager");
            Class<?> side = loadClass("net.minecraftforge.fml.relauncher.Side");
            patches = patchManager.getField("INSTANCE").get(null);
            patchManager.getMethod("setup", side).invoke(patches, side.getField("CLIENT").get(null));
            applyPatch = patchManager.getMethod("applyPatch", String.class, String.class, byte[].class);

            Class<?> manager = loadClass("gw");
            Class<?> state = loadClass("gx");
            Class<?> direction = loadClass("hu");
            Class<?> profile = loadClass("com.mojang.authlib.GameProfile");
            login = state.getField("d").get(null);
            play = state.getField("b").get(null);
            serverbound = direction.getField("a").get(null);
            clientbound = direction.getField("b").get(null);
            stateKey = (AttributeKey<Object>) manager.getField("c").get(null);
            networkChannel = manager.getDeclaredField("k");
            networkChannel.setAccessible(true);
            setState = manager.getMethod("a", state);
            managerConstructor = manager.getConstructor(direction);
            encoderConstructor = loadClass("ha").getConstructor(direction);
            profileConstructor = profile.getConstructor(UUID.class, String.class);
            loginPacketConstructor = loadClass("mh").getConstructor(profile);
            writeConstructor = loadClass("gw$4").getDeclaredConstructor(manager, state, state, loadClass("ht"),
                    GenericFutureListener[].class);
            writeConstructor.setAccessible(true);
        }

        @Override
        protected Class<?> findClass(String name) throws ClassNotFoundException {
            if (name.indexOf('.') >= 0) return super.findClass(name);
            URL resource = findResource(name + ".class");
            if (resource == null) throw new ClassNotFoundException(name);
            // Vanilla classes are in the obfuscated default package. Keep their
            // package consistent with the two Forge-patched siblings.
            try (InputStream stream = resource.openStream()) {
                byte[] bytes = IOUtils.toByteArray(stream);
                if ("gw".equals(name) || "gw$4".equals(name)) {
                    String deobfuscated = name.equals("gw") ? "NetworkManager" : "NetworkManager$4";
                    byte[] patched = (byte[]) applyPatch.invoke(patches, name,
                            "net.minecraft.network." + deobfuscated, bytes);
                    require(!Arrays.equals(bytes, patched), "Forge binary patch missing for " + deobfuscated);
                    bytes = patched;
                }
                return defineClass(name, bytes, 0, bytes.length);
            } catch (IOException | ReflectiveOperationException e) {
                throw new ClassNotFoundException(name, e);
            }
        }
    }
}
