package link.e4steam.retro.mixin;

import link.e4steam.steam.RetroSteamAuthentication;
import net.minecraft.network.Connection;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.ModifyConstant;

@Mixin(ServerGamePacketListenerImpl.class)
public abstract class ServerGamePacketListenerForge165Mixin {
    @Shadow public Connection connection;

    // Connectivity and similar Forge mods can own this constant. Honor the
    // higher-priority timeout policy when it has already replaced vanilla's.
    @ModifyConstant(method = "tick", constant = @Constant(longValue = 15_000L),
            require = 0, expect = 0, allow = 1)
    private long e4steam$extendAuthenticatedSteamKeepAlive(long vanillaInterval) {
        return RetroSteamAuthentication.authenticatedPeer(connection.getRemoteAddress()) == 0L
                ? vanillaInterval : 60_000L;
    }
}
