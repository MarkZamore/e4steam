package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.LockIconButton;
import net.minecraft.client.gui.screens.OptionsScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(OptionsScreen.class)
public abstract class LauncherOptionsScreenMixin extends Screen {
    @Shadow private Button difficultyButton;
    @Shadow private LockIconButton lockButton;

    protected LauncherOptionsScreenMixin(Component title) {
        super(title);
    }

    @Inject(method = "init", at = @At("TAIL"))
    private void e4steam$removeWorldOptions(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan() || minecraft.getSingleplayerServer() == null) return;
        if (difficultyButton != null) {
            buttons.remove(difficultyButton);
            children.remove(difficultyButton);
        }
        if (lockButton != null) {
            buttons.remove(lockButton);
            children.remove(lockButton);
        }
    }
}
