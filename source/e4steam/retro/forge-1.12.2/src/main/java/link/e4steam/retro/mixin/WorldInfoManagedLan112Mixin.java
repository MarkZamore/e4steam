package link.e4steam.retro.mixin;

import link.e4steam.retro.forge.WorldCommandPolicy112;
import net.minecraft.world.storage.WorldInfo;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(WorldInfo.class)
public abstract class WorldInfoManagedLan112Mixin {
    @Inject(method = "setAllowCommands", at = @At("HEAD"), cancellable = true)
    private void e4steam$keepInitialCommands(boolean requested, CallbackInfo result) {
        if (WorldCommandPolicy112.protectedWorld((WorldInfo) (Object) this)) result.cancel();
    }
}
