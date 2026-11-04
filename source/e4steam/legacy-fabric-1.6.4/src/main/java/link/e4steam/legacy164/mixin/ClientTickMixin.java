package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.Legacy164Client;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_1600",remap=false)
public abstract class ClientTickMixin {
    @Inject(method="method_2954",at=@At("HEAD"),require=1)
    private void e4steam$tick(CallbackInfo info){Legacy164Client.tick();}
}
