package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import net.minecraft.client.multiplayer.ThreadLanServerPing;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.net.DatagramSocket;

@Mixin(ThreadLanServerPing.class)
public abstract class ThreadLanServerPingManaged112Mixin {
    @Shadow @Final private DatagramSocket socket;

    @Inject(method = "run", at = @At("HEAD"), cancellable = true, remap = false)
    private void e4steam$skipNativeAdvertisement(CallbackInfo result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        socket.close();
        result.cancel();
    }
}
