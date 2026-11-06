package link.e4steam.legacy164.mixin;

import link.e4steam.legacy164.LegacyMessages;
import link.e4steam.legacy164.R;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

@Mixin(targets = "net.minecraft.class_393", remap = false)
public abstract class ShareMessageMixin {
    @ModifyArg(method = "method_1027", at = @At(value = "INVOKE",
        target = "Lnet/minecraft/class_1687;method_6020(Ljava/lang/String;[Ljava/lang/Object;)Lnet/minecraft/class_1687;"),
        index = 0, require = 1, allow = 1)
    private String e4steam$publishMessage(String key) {
        return LegacyMessages.publishKey(LegacyMessages.language(R.minecraft()), key);
    }
}
