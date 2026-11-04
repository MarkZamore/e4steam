package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyRegistry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(targets="net.minecraft.class_355",remap=false)
public abstract class SessionMixin {
    @Inject(method="method_5583",at=@At("RETURN"),cancellable=true,require=1)
    private void e4steam$localLabel(CallbackInfoReturnable<String> info){info.setReturnValue(LegacyRegistry.localLabel(info.getReturnValue()));}
}
