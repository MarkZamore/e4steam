package link.e4steam.retro.forge;

import io.netty.channel.ChannelFuture;

import java.util.function.Consumer;

public final class Forge112LoginHandshake {
    private Forge112LoginHandshake() {
    }

    public static void afterLoginSuccess(ChannelFuture loginWrite, Consumer<Runnable> scheduleServerTask,
                                         Runnable handshake) {
        loginWrite.addListener(write -> {
            if (!write.isSuccess()) return;
            scheduleServerTask.accept(() -> {
                if (loginWrite.channel().isActive()) handshake.run();
            });
        });
    }
}
