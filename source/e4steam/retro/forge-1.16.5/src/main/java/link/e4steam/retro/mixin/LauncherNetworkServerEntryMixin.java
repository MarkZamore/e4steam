package link.e4steam.retro.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import link.e4steam.retro.forge.LauncherLanServer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.screens.multiplayer.ServerSelectionList;
import net.minecraft.client.server.LanServer;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ServerSelectionList.NetworkServerEntry.class)
public abstract class LauncherNetworkServerEntryMixin {
    @Shadow @Final protected Minecraft minecraft;
    @Shadow @Final protected LanServer serverData;

    @Inject(method = "render", at = @At("HEAD"), cancellable = true)
    private void e4steam$drawSteamWorld(PoseStack pose, int row, int top, int left, int width, int height,
                                      int mouseX, int mouseY, boolean hovered, float partialTick, CallbackInfo info) {
        if (!(serverData instanceof LauncherLanServer)) return;
        LauncherLanServer world = (LauncherLanServer) serverData;
        Font font = minecraft.font;
        int x = left + 35;
        int availableWidth = Math.max(0, width - 35);
        font.draw(pose, font.plainSubstrByWidth(world.worldName(), availableWidth), x, top + 1, 0xFFFFFF);
        font.draw(pose, font.plainSubstrByWidth(world.getMotd(), availableWidth), x, top + 12, 0x808080);
        font.draw(pose, "Steam", x, top + 23, 0x303030);
        info.cancel();
    }
}
