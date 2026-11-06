package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.Legacy164Client;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_385",remap=false,priority=900)
public abstract class PauseMixin {
    @Redirect(method="method_1044",at=@At(value="INVOKE",target="Lnet/minecraft/class_601;method_1638()Z"),require=1,allow=1)
    private boolean e4steam$keepSharedActionEnabled(@Coerce Object server) {
        // This exact predicate only disables the local LAN button after
        // publication. The slot now opens the reporting notice in that state.
        return false;
    }

    @Inject(method="method_1044",at=@At("TAIL"),require=1)
    private void e4steam$reportCaption(CallbackInfo info) {
        Legacy164Client.updatePauseAction(this);
    }

    @Inject(method="method_1027",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$nativeShare(@Coerce Object button,CallbackInfo info){if(Legacy164Client.handlePauseAction(this,button))info.cancel();}
}
