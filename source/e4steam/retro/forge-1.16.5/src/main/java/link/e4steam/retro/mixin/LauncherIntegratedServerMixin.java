package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import net.minecraft.client.Minecraft;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.world.level.GameType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(IntegratedServer.class)
public abstract class LauncherIntegratedServerMixin {
    @Inject(method = "publishServer", at = @At("HEAD"), cancellable = true)
    private void e4steam$beginPublication(GameType mode, boolean commands, int port,
                                          CallbackInfoReturnable<Boolean> result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        IntegratedServer server = (IntegratedServer) (Object) this;
        if (server.isPublished() || !RetroBootstrap.beginPublication()) result.setReturnValue(false);
    }

    @ModifyVariable(method = "publishServer", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private GameType e4steam$keepWorldMode(GameType requested) {
        if (!RetroBootstrap.launcherManagedLan()) return requested;
        return ((IntegratedServer) (Object) this).getWorldData().getGameType();
    }

    @ModifyVariable(method = "publishServer", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private boolean e4steam$keepWorldCommands(boolean requested) {
        if (!RetroBootstrap.launcherManagedLan()) return requested;
        return ((IntegratedServer) (Object) this).getWorldData().getAllowCommands();
    }

    @Inject(method = "publishServer", at = @At("RETURN"))
    private void e4steam$finishPublication(GameType mode, boolean commands, int port,
                                           CallbackInfoReturnable<Boolean> result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        if (!result.getReturnValueZ()) {
            RetroBootstrap.cancelPublication();
            return;
        }
        IntegratedServer server = (IntegratedServer) (Object) this;
        String player = Minecraft.getInstance().getUser().getName();
        RetroBootstrap.publishRelay(server.getWorldData().getLevelName(), RetroBootstrap.launcherNickname(player));
    }
}
