package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.Legacy164Client;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_385",remap=false,priority=900)
public abstract class PauseMixin {
    @Inject(method="method_1027",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$nativeShare(@Coerce Object button,CallbackInfo info){if(Legacy164Client.shareFromPause(this,button))info.cancel();}
}
