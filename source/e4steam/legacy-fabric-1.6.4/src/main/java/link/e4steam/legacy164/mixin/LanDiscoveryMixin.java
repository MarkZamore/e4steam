package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyDiscovery;
import java.net.InetAddress;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_608",remap=false)
public abstract class LanDiscoveryMixin {
    @Inject(method="method_1659",at=@At("HEAD"),cancellable=true,require=1)
    private void e4steam$onlyManagedSteam(String announcement,InetAddress address,CallbackInfo info){if(LegacyDiscovery.nativeDiscoveryManaged(this))info.cancel();}
}
