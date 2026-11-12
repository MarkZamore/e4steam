package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import link.e4steam.retro.forge.WorldCommandPolicy112;
import net.minecraft.server.integrated.IntegratedServer;
import net.minecraft.server.management.PlayerList;
import net.minecraft.world.GameType;
import net.minecraft.world.WorldType;
import net.minecraft.world.storage.WorldInfo;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(IntegratedServer.class)
public abstract class IntegratedServerManagedLan112Mixin {
    @Unique private IntegratedServer e4steam$server() { return (IntegratedServer) (Object) this; }

    @Unique private WorldInfo e4steam$world() { return e4steam$server().getWorld(0).getWorldInfo(); }

    @Inject(method = "loadAllWorlds", at = @At("RETURN"))
    private void e4steam$protectSavedCommands(String fileName, String worldName, long seed,
            WorldType type, String options, CallbackInfo result) {
        if (RetroBootstrap.launcherManagedLan()) WorldCommandPolicy112.protect(e4steam$world());
    }

    @Inject(method = "shareToLAN", at = @At("HEAD"), cancellable = true)
    private void e4steam$beginShare(GameType gameType, boolean cheats, CallbackInfoReturnable<String> result) {
        if (RetroBootstrap.launcherManagedLan() && (e4steam$server().getPublic() || !RetroBootstrap.beginPublication())) {
            result.setReturnValue(null);
        }
    }

    @ModifyVariable(method = "shareToLAN", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private GameType e4steam$preserveMode(GameType requested) {
        return RetroBootstrap.launcherManagedLan() ? e4steam$world().getGameType() : requested;
    }

    @ModifyVariable(method = "shareToLAN", at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private boolean e4steam$preserveHostPermission(boolean requested) {
        return RetroBootstrap.launcherManagedLan() ? e4steam$world().areCommandsAllowed() : requested;
    }

    @Redirect(method = "shareToLAN", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/server/management/PlayerList;setCommandsAllowedForAll(Z)V"))
    private void e4steam$preserveGuestPermissions(PlayerList players, boolean requested) {
        players.setCommandsAllowedForAll(!RetroBootstrap.launcherManagedLan() && requested);
    }

    @Inject(method = "shareToLAN", at = @At("RETURN"))
    private void e4steam$completeShare(GameType gameType, boolean cheats, CallbackInfoReturnable<String> result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        if (result.getReturnValue() == null) RetroBootstrap.cancelPublication();
        else RetroBootstrap.publishRelay(e4steam$world().getWorldName(),
                RetroBootstrap.launcherNickname(e4steam$server().getServerOwner()));
    }
}
