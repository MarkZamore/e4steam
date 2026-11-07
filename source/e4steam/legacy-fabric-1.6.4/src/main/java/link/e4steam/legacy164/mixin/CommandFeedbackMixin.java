package link.e4steam.legacy164.mixin;

import link.e4steam.legacy164.LegacyMessages;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

@Mixin(targets="net.minecraft.class_1687",remap=false)
public abstract class CommandFeedbackMixin {
    @ModifyVariable(method="method_6020",at=@At("HEAD"),argsOnly=true,ordinal=0,require=1,allow=1)
    private static Object[] e4steam$displayNames(Object[] values,String key,Object[] original) {
        return LegacyMessages.commandNames(key,values);
    }
}
