package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyRegistry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
@Mixin(targets="net.minecraft.class_988",remap=false)
public abstract class PlayerDisplayMixin {
    @ModifyArg(method="method_5381",at=@At(value="INVOKE",target="Lnet/minecraft/class_1468;method_5565(Lnet/minecraft/class_1599;Ljava/lang/String;)Ljava/lang/String;"),index=1,require=1)
    private String e4steam$friendlyName(String nativeName){return LegacyRegistry.displayName(nativeName);}
}
