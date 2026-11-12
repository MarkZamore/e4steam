package link.e4steam.retro.mixin;

import java.net.DatagramSocket;
import link.e4steam.retro.RetroBootstrap;
import net.minecraft.client.server.LanServerPinger;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(LanServerPinger.class)
public abstract class LauncherLanPingerMixin {
    @Shadow @Final private DatagramSocket socket;

    @Inject(method = "run", at = @At("HEAD"), cancellable = true, remap = false)
    private void e4steam$skipLanBroadcast(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        socket.close();
        info.cancel();
    }
}
