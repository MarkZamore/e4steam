package link.e4steam.retro.mixin;

import link.e4steam.retro.forge.SteamLanServerInfo112;
import net.minecraft.client.gui.ServerListEntryLanDetected;
import net.minecraft.client.network.LanServerInfo;
import net.minecraft.client.resources.I18n;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(ServerListEntryLanDetected.class)
public abstract class ServerListEntryManagedLan112Mixin {
    @Shadow @Final protected LanServerInfo serverData;

    @Redirect(method = "drawEntry", at = @At(value = "INVOKE", ordinal = 0, target =
            "Lnet/minecraft/client/resources/I18n;format(Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;"))
    private String e4steam$showWorldName(String key, Object[] parameters) {
        if (serverData instanceof SteamLanServerInfo112) return ((SteamLanServerInfo112) serverData).title();
        return I18n.format(key, parameters);
    }

    @Redirect(method = "drawEntry", at = @At(value = "INVOKE", target =
            "Lnet/minecraft/client/network/LanServerInfo;getServerIpPort()Ljava/lang/String;"))
    private String e4steam$showSteamTransport(LanServerInfo entry) {
        return entry instanceof SteamLanServerInfo112 ? "Steam" : entry.getServerIpPort();
    }
}
