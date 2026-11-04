package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.R;
import link.e4steam.steam.SteamRuntime;
import java.net.SocketAddress;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(targets="net.minecraft.class_469",remap=false)
public abstract class ClientLoginMixin {
    @Inject(method="method_1884",at=@At("RETURN"),require=1)
    private void e4steam$nativeAccepted(@Coerce Object login,CallbackInfo info){Object net=R.get(this,"field_1622");if(net!=null&&net.getClass().getName().equals("net.minecraft.class_633"))SteamRuntime.get().clientMinecraftJoined((SocketAddress)R.call(net,"method_1770"));}
}
