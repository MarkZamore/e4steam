package link.e4steam.legacy164;

import link.e4steam.steam.SteamRuntime;
import java.net.SocketAddress;
import java.util.*;

/** Ownership comes from a live Steam bridge, or the proven native memory pair. */
public final class LegacyIdentity {
    private record LocalProof(Object clientConnection,String nativeName,long steamId) {}
    private static final Map<Object,LocalProof> locals=Collections.synchronizedMap(new WeakHashMap<>());
    private LegacyIdentity() {}
    public static String canonicalName(long id){return LegacyRegistry.canonicalName(id);}
    public static long remotePeer(Object tcp){return SteamRuntime.get().authenticatedMinecraftPeer((SocketAddress)R.call(tcp,"method_1770"));}
    public static boolean authenticated(Object login) {return remotePeer(R.get(login,"field_2882"))!=0;}
    public static void prepareRemote(Object login,Object protocol) {
        long peer=remotePeer(R.get(login,"field_2882"));
        if(peer==0)throw new SecurityException("An authenticated Steam connection is required");
        R.set(protocol,"field_2422",canonicalName(peer));
    }
    public static void verifyRemote(Object login) {
        Object tcp=R.get(login,"field_2882");long peer=remotePeer(tcp);
        if(peer==0||!canonicalName(peer).equals(R.get(login,"field_2888")))throw new SecurityException("Steam identity is no longer bound to this connection");
        rejectDuplicate(R.call(R.get(login,"field_2886"),"method_3004"),canonicalName(peer));
    }
    public static String registerLocal(Object listener,Object memory,String requested) {
        Object server=R.call(listener,"method_1643"),mc=R.get(server,"field_2204");
        Object handler=R.get(memory,"field_2307");
        if(R.call(mc,"method_2909")!=server||R.get(handler,"field_1623")!=mc||R.get(handler,"field_1622")!=memory)
            throw new SecurityException("The native host memory connection is not owned by this client");
        LegacyRegistry.Entry entry=LegacyRegistry.entry(requested);
        if(entry==null||!entry.uuid().toString().equals(System.getProperty("minecraft.portable.identity.localPlayer","")))throw new SecurityException("The native host is not the launcher's local profile");
        long own=entry.steamId();String canonical=canonicalName(own);
        long runtimeId=currentRuntimeAccount();
        if(runtimeId!=0&&runtimeId!=own)throw new SecurityException("Launcher and Steam host identity do not match");
        locals.put(listener,new LocalProof(memory,canonical,own));
        return canonical;
    }
    public static void verifyAdmission(Object manager,Object connection,Object player) {
        Object server=R.call(manager,"method_2023");String nativeName=(String)R.get(player,"field_3982");
        if(connection.getClass().getName().equals("net.minecraft.class_632")) {
            Object listener=R.call(server,"method_1637");LocalProof proof=locals.get(listener);
            if(proof==null||R.get(listener,"field_2212")!=connection||R.call(connection,"method_1780")!=proof.clientConnection||!proof.nativeName.equals(nativeName))throw new SecurityException("Unproven local host admission");
            long runtimeId=currentRuntimeAccount();if(runtimeId!=0&&runtimeId!=proof.steamId)throw new SecurityException("Steam host account changed");
        } else {
            long peer=remotePeer(connection);
            if(peer==0||!canonicalName(peer).equals(nativeName))throw new SecurityException("Unproven remote admission");
        }
        rejectDuplicate(manager,nativeName);
    }
    public static void rejectDuplicate(Object manager,String name) {
        for(Object existing:(List<?>)R.get(manager,"field_2708"))if(name.equals(R.get(existing,"field_3982")))throw new SecurityException("This Steam account is already connected");
    }
    private static long currentRuntimeAccount(){String value=SteamRuntime.get().steamId();try{return Long.parseUnsignedLong(value);}catch(NumberFormatException unavailable){return 0;}}
    public static void closed(Object server) {Object listener=R.get(server,"field_2206");locals.remove(listener);}
    public static String resolveAlias(Object manager,String input) {
        if(input==null)return null;
        String found=null;
        for(Object player:(List<?>)R.get(manager,"field_2708")) {
            String nativeName=(String)R.get(player,"field_3982");
            if(nativeName.equals(input))return input;
            if(LegacyRegistry.displayName(nativeName).equalsIgnoreCase(input)) {if(found!=null)return input;found=nativeName;}
        }
        return found==null?input:found;
    }
    /** Native command parsing splits on whitespace; retain canonical fallbacks
     * for ambiguous or multi-token historical display names. */
    public static String[] completionNames(String[] nativeNames){
        Map<String,Integer> counts=new HashMap<>();
        for(String name:nativeNames){String display=LegacyRegistry.displayName(name);counts.merge(display.toLowerCase(Locale.ROOT),1,Integer::sum);}
        String[] result=nativeNames.clone();
        for(int i=0;i<result.length;i++){
            String display=LegacyRegistry.displayName(result[i]);
            if(counts.get(display.toLowerCase(Locale.ROOT))==1&&!display.startsWith("@")&&display.codePoints().noneMatch(Character::isWhitespace))result[i]=display;
        }
        return result;
    }
}
