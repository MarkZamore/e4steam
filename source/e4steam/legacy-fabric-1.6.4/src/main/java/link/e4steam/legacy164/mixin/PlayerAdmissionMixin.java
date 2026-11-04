package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyIdentity;
import link.e4steam.legacy164.R;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(targets="net.minecraft.class_743",remap=false)
public abstract class PlayerAdmissionMixin {
    @Inject(method="method_1980",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$admit(@Coerce Object connection,@Coerce Object player,CallbackInfo info){try{LegacyIdentity.verifyAdmission(this,connection,player);}catch(SecurityException denied){R.call(connection,"method_1768",denied.getMessage(),new Object[0]);info.cancel();}}
    @ModifyVariable(method="method_2010",at=@At("HEAD"),argsOnly=true,index=1,require=1)
    private String e4steam$commandAlias(String name){return LegacyIdentity.resolveAlias(this,name);}
    @Inject(method="method_2002",at=@At("RETURN"),cancellable=true,require=1)
    private void e4steam$commandCompletions(CallbackInfoReturnable<String[]> info){info.setReturnValue(LegacyIdentity.completionNames(info.getReturnValue()));}
}
