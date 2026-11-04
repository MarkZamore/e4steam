package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyIdentity;
import link.e4steam.legacy164.R;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_801",remap=false)
public abstract class LoginMixin {
    @Inject(method="method_1861",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$authenticate(@Coerce Object protocol,CallbackInfo info){try{LegacyIdentity.prepareRemote(this,protocol);}catch(SecurityException denied){R.call(this,"method_2190",denied.getMessage());info.cancel();}}
    @Redirect(method={"method_1861","method_1859"},at=@At(value="INVOKE",target="Lnet/minecraft/server/MinecraftServer;method_2984()Z"),require=2)
    private boolean e4steam$sessionAuthentication(@Coerce Object server){return !LegacyIdentity.authenticated(this)&&Boolean.TRUE.equals(R.call(server,"method_2984"));}
    @Inject(method="method_2194",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$recheck(CallbackInfo info){try{LegacyIdentity.verifyRemote(this);}catch(SecurityException denied){R.call(this,"method_2190",denied.getMessage());info.cancel();}}
}
