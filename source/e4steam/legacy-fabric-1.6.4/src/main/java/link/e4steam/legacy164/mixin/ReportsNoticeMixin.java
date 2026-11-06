package link.e4steam.legacy164.mixin;

import link.e4steam.legacy164.Legacy164Client;
import link.e4steam.legacy164.R;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

@Mixin(targets = "net.minecraft.class_475", remap = false)
public abstract class ReportsNoticeMixin {
    @ModifyArg(method = "method_1044", at = @At(value = "INVOKE",
        target = "Lnet/minecraft/class_356;<init>(IIILjava/lang/String;)V"),
        index = 3, require = 1, allow = 1)
    private String e4steam$doneButton(String caption) {
        return Legacy164Client.isReportsNotice(this)
            ? (String) R.call(R.type("net.minecraft.class_1664"), "method_5933", "gui.done")
            : caption;
    }
}
