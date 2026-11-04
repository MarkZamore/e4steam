package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyDiscovery;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_376",remap=false)
public abstract class DiscoveryMixin {
    @Inject(method="method_1044",at=@At("RETURN"),require=1)
    private void e4steam$open(CallbackInfo info){LegacyDiscovery.begin(this);}
    @Inject(method="method_1030",at=@At("HEAD"),require=1)
    private void e4steam$close(CallbackInfo info){LegacyDiscovery.end(this);}
    @Inject(method="method_1003",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$join(@Coerce Object data,CallbackInfo info){if(LegacyDiscovery.join(this,data))info.cancel();}
}
