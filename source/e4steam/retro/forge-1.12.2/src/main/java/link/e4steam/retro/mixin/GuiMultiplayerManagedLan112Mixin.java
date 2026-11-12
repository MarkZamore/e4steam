package link.e4steam.retro.mixin;

import link.e4steam.retro.RetroBootstrap;
import link.e4steam.retro.forge.SteamLanServerInfo112;
import link.e4steam.steam.SteamRuntime;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiMultiplayer;
import net.minecraft.client.gui.ServerSelectionList;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.network.LanServerInfo;
import net.minecraft.util.text.TextComponentTranslation;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Mixin(GuiMultiplayer.class)
public abstract class GuiMultiplayerManagedLan112Mixin {
    @Shadow private ServerSelectionList serverListSelector;
    @Unique private long e4steam$nextPoll;
    @Unique private List<String> e4steam$shown = Collections.emptyList();

    @Redirect(method = "updateScreen", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/client/gui/ServerSelectionList;updateNetworkServers(Ljava/util/List;)V"))
    private void e4steam$ignoreNativeDiscovery(ServerSelectionList list, List<LanServerInfo> servers) {
        if (!RetroBootstrap.launcherManagedLan()) list.updateNetworkServers(servers);
    }

    @Inject(method = "initGui", at = @At("RETURN"))
    private void e4steam$refreshOnOpen(CallbackInfo result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        e4steam$shown = Collections.emptyList();
        e4steam$nextPoll = 0;
        serverListSelector.updateNetworkServers(Collections.emptyList());
    }

    @Inject(method = "updateScreen", at = @At("RETURN"))
    private void e4steam$refreshSteamWorlds(CallbackInfo result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        long now = System.nanoTime();
        if (e4steam$nextPoll != 0 && now - e4steam$nextPoll < 0) return;
        e4steam$nextPoll = now + TimeUnit.SECONDS.toNanos(3);
        Minecraft client = Minecraft.getMinecraft();
        SteamRuntime.get().discoverLauncherWorlds().whenComplete((worlds, failure) -> client.addScheduledTask(() -> {
            if (client.currentScreen != (Object) this) return;
            List<LanServerInfo> rows = new ArrayList<>();
            List<String> labels = new ArrayList<>();
            if (failure == null) worlds.forEach(world -> {
                rows.add(new SteamLanServerInfo112(world));
                labels.add(world.address() + "\n" + world.worldName() + "\n" + world.playerName());
            });
            if (!labels.equals(e4steam$shown)) {
                serverListSelector.updateNetworkServers(rows);
                e4steam$shown = labels;
            }
        }));
    }

    @Inject(method = "connectToServer", at = @At("HEAD"), cancellable = true)
    private void e4steam$connectToSteam(ServerData target, CallbackInfo result) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        CompletableFuture<Boolean> join = SteamRuntime.get().connectLauncherWorld(target.serverIP);
        if (join == null) return;
        result.cancel();
        Minecraft client = Minecraft.getMinecraft();
        join.whenComplete((started, failure) -> {
            if (Boolean.TRUE.equals(started)) return;
            client.addScheduledTask(() -> client.ingameGUI.getChatGUI().printChatMessage(
                    new TextComponentTranslation("text.e4steam_minecraft.launcherWorldUnavailable")));
        });
    }
}
