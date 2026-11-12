package link.e4steam.retro.mixin;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.TimeUnit;
import link.e4steam.E4steamClient;
import link.e4steam.retro.forge.LauncherLanServer;
import link.e4steam.retro.RetroBootstrap;
import link.e4steam.steam.SteamLanWorld;
import link.e4steam.steam.SteamRuntime;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.multiplayer.ServerSelectionList;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.server.LanServer;
import net.minecraft.client.server.LanServerDetection;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(JoinMultiplayerScreen.class)
public abstract class LauncherJoinMultiplayerScreenMixin {
    @Shadow private ServerSelectionList serverSelectionList;
    @Unique private CompletableFuture<List<SteamLanWorld>> e4steam$discovery;
    @Unique private List<LanServer> e4steam$shownWorlds = Collections.emptyList();
    @Unique private long e4steam$lastPoll = System.nanoTime();

    @Inject(method = "init", at = @At("TAIL"))
    private void e4steam$beginDiscovery(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        SteamRuntime.get().startAtGameLaunchAsync();
        e4steam$lastPoll = System.nanoTime() - TimeUnit.SECONDS.toNanos(2);
    }

    @Redirect(method = "tick", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/client/server/LanServerDetection$LanServerList;isDirty()Z"))
    private boolean e4steam$showNativeResults(LanServerDetection.LanServerList list) {
        return !RetroBootstrap.launcherManagedLan() && list.isDirty();
    }

    @Inject(method = "tick", at = @At("TAIL"))
    private void e4steam$pollSteam(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        if (e4steam$discovery != null && e4steam$discovery.isDone()) {
            List<LanServer> found = new ArrayList<>();
            try {
                for (SteamLanWorld world : e4steam$discovery.join()) found.add(new LauncherLanServer(world));
            } catch (CompletionException unavailable) {
                // No Steam rows when the Steam worker is unavailable.
            }
            e4steam$discovery = null;
            if (!found.equals(e4steam$shownWorlds)) {
                serverSelectionList.updateNetworkServers(found);
                e4steam$shownWorlds = found;
            }
        }
        long now = System.nanoTime();
        if (e4steam$discovery == null && now - e4steam$lastPoll >= TimeUnit.SECONDS.toNanos(2)) {
            e4steam$lastPoll = now;
            e4steam$discovery = SteamRuntime.get().discoverLauncherWorlds();
        }
    }

    @Inject(method = "removed", at = @At("TAIL"))
    private void e4steam$endDiscovery(CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan()) return;
        e4steam$discovery = null;
        if (!e4steam$shownWorlds.isEmpty()) {
            serverSelectionList.updateNetworkServers(Collections.emptyList());
            e4steam$shownWorlds = Collections.emptyList();
        }
    }

    @Inject(method = "join", at = @At("HEAD"), cancellable = true)
    private void e4steam$joinSteamWorld(ServerData target, CallbackInfo info) {
        if (!RetroBootstrap.launcherManagedLan() || !target.isLan()) return;
        CompletableFuture<Boolean> request = SteamRuntime.get().connectLauncherWorld(target.ip);
        if (request == null) return;
        info.cancel();
        request.whenComplete((accepted, failure) -> {
            if (failure != null || !Boolean.TRUE.equals(accepted)) {
                E4steamClient.showSteamJoinFailure(failure == null ? "Steam world is no longer available" : failure);
            }
        });
    }
}
