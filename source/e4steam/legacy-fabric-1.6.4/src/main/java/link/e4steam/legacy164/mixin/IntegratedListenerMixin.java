package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyIdentity;
import java.net.InetAddress;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_604",remap=false)
public abstract class IntegratedListenerMixin {
    @Inject(method="method_1641",at=@At("HEAD"),require=1)
    private void e4steam$proveNativeHost(@Coerce Object memory,String name,CallbackInfo info){LegacyIdentity.registerLocal(this,memory,name);}
    @ModifyArg(method="method_1642",at=@At(value="INVOKE",target="Lnet/minecraft/class_775;<init>(Lnet/minecraft/class_805;Ljava/net/InetAddress;I)V"),index=1,require=1)
    private InetAddress e4steam$loopback(InetAddress ignored) throws java.net.UnknownHostException{return InetAddress.getByAddress(new byte[]{127,0,0,1});}
}
