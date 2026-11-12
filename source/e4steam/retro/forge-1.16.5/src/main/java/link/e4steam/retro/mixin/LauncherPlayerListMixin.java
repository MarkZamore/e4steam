package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import com.mojang.authlib.GameProfile;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.players.PlayerList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(PlayerList.class)
public abstract class LauncherPlayerListMixin {
    @Shadow public abstract MinecraftServer getServer();

    @Inject(method = "isOp", at = @At("HEAD"), cancellable = true)
    private void e4steam$checkWorldCommands(GameProfile player, CallbackInfoReturnable<Boolean> result) {
        if (e4steam$worldCommandsDisabled()) result.setReturnValue(false);
    }

    @ModifyVariable(method = "setAllowCheatsForAllPlayers", at = @At("HEAD"), argsOnly = true)
    private boolean e4steam$keepWorldCommandsDisabled(boolean requested) {
        return requested && !e4steam$worldCommandsDisabled();
    }

    @Unique
    private boolean e4steam$worldCommandsDisabled() {
        if (!RetroBootstrap.launcherManagedLan()) return false;
        MinecraftServer server = getServer();
        return server instanceof IntegratedServer && !server.getWorldData().getAllowCommands();
    }
}
