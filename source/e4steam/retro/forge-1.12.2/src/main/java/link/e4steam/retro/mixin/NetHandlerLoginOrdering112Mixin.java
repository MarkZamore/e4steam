package link.e4steam.retro.mixin;

import io.netty.channel.Channel;
import io.netty.channel.ChannelPromise;
import link.e4steam.retro.forge.Forge112LoginHandshake;
import link.e4steam.steam.RetroSteamAuthentication;
import net.minecraft.entity.player.EntityPlayerMP;
import net.minecraft.network.NetworkManager;
import net.minecraft.network.Packet;
import net.minecraft.network.login.server.SPacketLoginSuccess;
import net.minecraft.server.management.PlayerList;
import net.minecraft.server.network.NetHandlerLoginServer;
import net.minecraftforge.fml.common.network.internal.FMLNetworkHandler;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(NetHandlerLoginServer.class)
public abstract class NetHandlerLoginOrdering112Mixin {
    @Unique private ChannelPromise e4steam$loginSuccessWrite;

    @Inject(method = "tryAcceptPlayer", at = @At("HEAD"), cancellable = true)
    private void e4steam$acceptOnce(CallbackInfo result) {
        // The delayed-player path sets READY_TO_ACCEPT before handing off to
        // Forge. Do not send LoginSuccess again while the handoff is pending.
        if (e4steam$loginSuccessWrite != null) result.cancel();
    }

    @Redirect(method = "tryAcceptPlayer", at = @At(value = "INVOKE", target =
            "Lnet/minecraft/network/NetworkManager;sendPacket(Lnet/minecraft/network/Packet;)V"))
    private void e4steam$writeLoginSuccess(NetworkManager manager, Packet<?> packet) {
        if (!(packet instanceof SPacketLoginSuccess)
                || RetroSteamAuthentication.authenticatedPeer(manager.getRemoteAddress()) == 0L) {
            manager.sendPacket(packet);
            return;
        }

        Channel channel = manager.channel();
        ChannelPromise loginWrite = channel.newPromise();
        e4steam$loginSuccessWrite = loginWrite;
        // The peer can send PLAY packets as soon as it receives LoginSuccess.
        // Forge resumes reads when it starts the handshake on the server thread.
        channel.config().setAutoRead(false);
        manager.sendPacket(packet, write -> {
            if (write.isSuccess()) loginWrite.setSuccess();
            else loginWrite.setFailure(write.cause());
        });
    }

    @Redirect(method = {"tryAcceptPlayer", "update"}, require = 2, allow = 2,
            at = @At(value = "INVOKE", remap = false, target =
                    "Lnet/minecraftforge/fml/common/network/internal/FMLNetworkHandler;fmlServerHandshake("
                    + "Lnet/minecraft/server/management/PlayerList;Lnet/minecraft/network/NetworkManager;"
                    + "Lnet/minecraft/entity/player/EntityPlayerMP;)V"))
    private void e4steam$startForgeHandshake(PlayerList players, NetworkManager manager, EntityPlayerMP player) {
        ChannelPromise loginWrite = e4steam$loginSuccessWrite;
        if (loginWrite == null) {
            FMLNetworkHandler.fmlServerHandshake(players, manager, player);
            return;
        }

        // Forge sets PLAY synchronously. Wait until Netty has encoded and
        // written LoginSuccess in LOGIN, including on the delayed-player path.
        Forge112LoginHandshake.afterLoginSuccess(loginWrite, task -> players.getServerInstance().addScheduledTask(task),
                () -> {
                    if (manager.getNetHandler() == (Object) this) {
                        FMLNetworkHandler.fmlServerHandshake(players, manager, player);
                    }
                });
    }
}
