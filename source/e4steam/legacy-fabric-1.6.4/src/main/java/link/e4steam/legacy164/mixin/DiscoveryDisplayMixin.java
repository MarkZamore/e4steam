package link.e4steam.legacy164.mixin;
import link.e4steam.legacy164.LegacyDiscovery;
import link.e4steam.legacy164.R;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
@Mixin(targets="net.minecraft.class_377",remap=false)
public abstract class DiscoveryDisplayMixin {
    @Redirect(method="method_1018",at=@At(value="INVOKE",target="Lnet/minecraft/class_1664;method_5933(Ljava/lang/String;)Ljava/lang/String;"),require=2)
    private String e4steam$worldTitle(String key,int index,int x,int y,int height,@Coerce Object renderer){String original=(String)R.call(R.type("net.minecraft.class_1664"),"method_5933",key);return key.equals("lanServer.title")?LegacyDiscovery.worldTitle(original,LegacyDiscovery.entryAt(this,index)):original;}
    @Redirect(method="method_1018",at=@At(value="INVOKE",target="Lnet/minecraft/class_606;method_1656()Ljava/lang/String;"),require=1)
    private String e4steam$serviceLabel(@Coerce Object entry){return LegacyDiscovery.displayAddress((String)R.call(entry,"method_1656"),entry);}
    @Redirect(method="method_1019",at=@At(value="INVOKE",target="Lnet/minecraft/class_1664;method_5933(Ljava/lang/String;)Ljava/lang/String;"),require=1)
    private String e4steam$scanningLabel(String key){Object screen=R.get(this,"field_1200");return key.equals("lanServer.scanning")&&LegacyDiscovery.managedScreen(screen)?"Steam":(String)R.call(R.type("net.minecraft.class_1664"),"method_5933",key);}
}
