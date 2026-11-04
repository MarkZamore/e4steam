package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyIdentity;
import link.e4steam.legacy164.LegacyPublication;
import link.e4steam.legacy164.R;
import link.e4steam.retro.RetroBootstrap;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.*;
@Mixin(targets="net.minecraft.class_601",remap=false)
public abstract class IntegratedServerMixin {
    @Inject(method="method_3000",at=@At("RETURN"),require=1)
    private void e4steam$published(@Coerce Object gameType,boolean commands,CallbackInfoReturnable<String> info){if(info.getReturnValue()!=null){int port=Integer.parseInt((String)R.call(R.get(this,"field_2206"),"method_1642"));RetroBootstrap.relayBound(port);LegacyPublication.published(R.get(this,"field_2204"),this,port);}}
    @Inject(method="method_3044",at=@At("HEAD"),require=1)
    private void e4steam$serverTasks(CallbackInfo info){LegacyPublication.tick(this);}
    @Inject(method={"method_3034","method_3038"},at=@At("HEAD"),require=2)
    private void e4steam$closed(CallbackInfo info){LegacyPublication.closed(this);RetroBootstrap.relayClosed();LegacyIdentity.closed(this);}
}
