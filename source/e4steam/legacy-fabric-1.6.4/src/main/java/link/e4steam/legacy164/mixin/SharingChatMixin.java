package link.e4steam.legacy164.mixin;

import link.e4steam.legacy164.LegacySharingChat;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(targets="net.minecraft.class_359",remap=false)
public abstract class SharingChatMixin {
    @Inject(method="method_1026",at=@At("HEAD"),cancellable=true,require=1,allow=1)
    private void e4steam$sharingClick(int x,int y,int button,CallbackInfo info) {
        if(LegacySharingChat.click(button))info.cancel();
    }
}
