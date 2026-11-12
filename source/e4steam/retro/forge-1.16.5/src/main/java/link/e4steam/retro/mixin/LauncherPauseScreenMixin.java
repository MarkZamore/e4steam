package link.e4steam.retro.mixin;

import link.e4steam.E4steamClient;
import link.e4steam.retro.RetroBootstrap;
import net.minecraft.ChatFormatting;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.PauseScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.TextComponent;
import net.minecraft.network.chat.TranslatableComponent;
import net.minecraft.util.HttpUtil;
import net.minecraft.world.level.storage.WorldData;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(PauseScreen.class)
public abstract class LauncherPauseScreenMixin extends Screen {
    protected LauncherPauseScreenMixin(Component title) {
        super(title);
    }

    @Inject(method = "createPauseMenu", at = @At("TAIL"))
    private void e4steam$replaceLanButton(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        IntegratedServer server = minecraft.getSingleplayerServer();
        if (server == null) return;
        for (int index = 0; index < buttons.size(); index++) {
            AbstractWidget old = buttons.get(index);
            Component label = old.getMessage();
            if (!(label instanceof TranslatableComponent)
                    || !((TranslatableComponent) label).getKey().equals("menu.shareToLan")) continue;
            int childIndex = children.indexOf(old);
            if (childIndex < 0) return;
            Button replacement = new Button(old.x, old.y, old.getWidth(), old.getHeight(),
                    server.isPublished() ? new TranslatableComponent("text.e4steam_lanmc.reports") : label,
                    ignored -> e4steam$useLanButton(server));
            buttons.set(index, replacement);
            children.set(childIndex, replacement);
            return;
        }
    }

    @Unique
    private void e4steam$useLanButton(IntegratedServer server) {
        if (minecraft.getSingleplayerServer() != server) return;
        if (server.isPublished()) {
            RetroBootstrap.openReports();
            return;
        }
        int port = HttpUtil.getAvailablePort();
        WorldData world = server.getWorldData();
        boolean published = false;
        try {
            published = server.publishServer(world.getGameType(), world.getAllowCommands(), port);
        } catch (RuntimeException exception) {
            E4steamClient.LOGGER.error("Could not open the integrated world", exception);
        } finally {
            RetroBootstrap.cancelPublication();
        }
        minecraft.gui.getChat().addMessage(published
                ? new TranslatableComponent("text.e4steam_lanmc.localPort",
                        new TextComponent(Integer.toString(port)).withStyle(ChatFormatting.GREEN))
                : new TranslatableComponent("commands.publish.failed"));
        if (published) minecraft.setScreen(null);
    }
}
