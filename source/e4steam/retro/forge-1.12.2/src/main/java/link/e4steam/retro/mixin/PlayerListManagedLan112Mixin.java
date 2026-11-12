package link.e4steam.retro.mixin;

import com.mojang.authlib.GameProfile;
import link.e4steam.retro.RetroBootstrap;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.integrated.IntegratedServer;
import net.minecraft.server.management.PlayerList;
import net.minecraft.world.WorldServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(PlayerList.class)
public abstract class PlayerListManagedLan112Mixin {
    @Shadow public abstract MinecraftServer getServerInstance();

    @Inject(method = "setCommandsAllowedForAll", at = @At("HEAD"), cancellable = true)
    private void e4steam$rejectAllPlayerGrant(boolean requested, CallbackInfo result) {
        if (requested && RetroBootstrap.launcherManagedLan() && getServerInstance() instanceof IntegratedServer) {
            result.cancel();
        }
    }

    @Inject(method = "canSendCommands", at = @At("HEAD"), cancellable = true)
    private void e4steam$enforceSavedPermission(GameProfile player, CallbackInfoReturnable<Boolean> result) {
        MinecraftServer server = getServerInstance();
        if (!RetroBootstrap.launcherManagedLan() || !(server instanceof IntegratedServer)) return;
        WorldServer world = server.getWorld(0);
        if (world == null || !world.getWorldInfo().areCommandsAllowed()) result.setReturnValue(false);
    }
}
