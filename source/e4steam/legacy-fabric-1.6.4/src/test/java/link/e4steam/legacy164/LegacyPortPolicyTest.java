package link.e4steam.legacy164;

import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import link.e4steam.steam.SteamRuntime;

/** Deterministic ownership negatives. These are not authenticated Steam gameplay. */
public final class LegacyPortPolicyTest {
    static final class Connection { public SocketAddress method_1770(){return new InetSocketAddress("127.0.0.1",43210);} }
    static final class Login { public final Connection field_2882=new Connection(); }
    static final class Protocol { public String field_2422="Untrusted"; }
    static final class ServerData { public String field_1687;ServerData(String address){field_1687=address;} }
    static final class Player { public String field_3982; Player(String name){field_3982=name;} }
    static final class Manager { public List<Player> field_2708=new ArrayList<>(); }
    private static int assertions;
    private static void check(boolean value,String message){assertions++;if(!value)throw new AssertionError(message);}
    private static void denied(Runnable action,String message){try{action.run();throw new AssertionError(message);}catch(SecurityException expected){assertions++;}}
    public static void main(String[]args)throws Exception{
        org.apache.logging.log4j.LogManager.getLogger("e4steam").info("Starting source-port ownership negative checks");
        // Synthetic numbers below exercise encoding only, never grant a Steam session.
        check(LegacyRegistry.canonicalName(1).equals("s0000000000001"),"Fixed-width minimum key");
        check(LegacyRegistry.canonicalName(-1L).length()==14,"Unsigned64 key fits legacy username");
        Set<String> keys=new HashSet<>();for(long id:new long[]{1,35,36,Long.MAX_VALUE,Long.MIN_VALUE,-1})check(keys.add(LegacyRegistry.canonicalName(id)),"Distinct unsigned boundary encodings");
        check(SteamRuntime.get().authenticatedMinecraftPeer(new InetSocketAddress("127.0.0.1",43210))==0,"Unknown loopback socket is not authenticated");
        check(SteamRuntime.get().authenticatedMinecraftPeer(new InetSocketAddress("192.0.2.1",43210))==0,"Non-loopback socket is not authenticated");
        Protocol protocol=new Protocol();denied(()->LegacyIdentity.prepareRemote(new Login(),protocol),"A label must not authenticate TCP");
        check(protocol.field_2422.equals("Untrusted"),"Denied login did not rewrite packet identity");
        check(LegacyDiscovery.description(null,"LauncherName","NativeWorld")==null,"Persona-only lobby metadata is not advertised");
        check(LegacyDiscovery.description("0","LauncherName","NativeWorld")==null,"Partially written description remains hidden");
        check(LegacyDiscovery.description("1","","NativeWorld")==null,"Missing launcher host label is not guessed");
        check(LegacyDiscovery.description("1","LauncherName"," ")==null,"Missing native world title is not guessed");
        check(Arrays.equals(LegacyDiscovery.description("1","LauncherName","NativeWorld"),new String[]{"LauncherName","NativeWorld"}),"Shared lobby description protocol returns both native labels");
        Object unmanaged=new Object();
        check(LegacyDiscovery.worldTitle("LAN",unmanaged).equals("LAN"),"Unmanaged native LAN title remains native");
        check(LegacyDiscovery.displayAddress("192.0.2.1:1234",unmanaged).equals("192.0.2.1:1234"),"Unmanaged native address is preserved");
        check(!LegacyDiscovery.nativeDiscoveryManaged(unmanaged),"LAN suppression is scoped to a managed collection");
        check(!LegacyDiscovery.join(unmanaged,new ServerData("example.invalid:25565")),"Manual saved servers keep the native join path");
        check(LegacyDiscovery.join(unmanaged,new ServerData("e4steam-legacy-1.invalid")),"A stale synthetic discovery entry cannot fall through to DNS");
        String publish = LegacyMessages.publishKey("ru_RU", "commands.publish.started");
        check(String.format(Locale.ROOT, publish, "43120").equals("Порт локального сервера: 43120"),
            "Russian success text matches the modern client and still shows the bound port");
        check(LegacyMessages.publishKey("ru_RU", "commands.publish.failed").equals("commands.publish.failed"),
            "Publication failure keeps the native message");
        check(LegacyMessages.publishKey("en_US", "commands.publish.started").equals("commands.publish.started"),
            "English already uses the modern success text");
        check(LegacyMessages.reportsUnavailable("ru_RU").equals("Жалобы на игроков в этой версии недоступны."),
            "Legacy reporting action explains the actual limitation");
        String emoji="😀".repeat(70);String clean=LegacyPublication.cleanName(emoji);check(clean.codePointCount(0,clean.length())==64&&!Character.isHighSurrogate(clean.charAt(clean.length()-1)),"Description bounds preserve complete Unicode code points");
        Path directory=Files.createTempDirectory("e4steam-legacy-policy-");Path registry=directory.resolve("registry.txt");
        try{
            UUID uuid=UUID.randomUUID();String nativeName=LegacyRegistry.canonicalName(1),display="Игрок | Один";
            String encoded=Base64.getEncoder().encodeToString(display.getBytes(StandardCharsets.UTF_8));
            Files.writeString(registry,"1|"+nativeName+"|"+encoded+"|"+uuid+"\n",StandardCharsets.UTF_8);
            System.setProperty("minecraft.portable.legacy.registry",registry.toString());System.setProperty("minecraft.portable.identity.localPlayer",uuid.toString());
            check(LegacyRegistry.displayName(nativeName).equals(display),"Unicode and separator display alias round trip");
            check(LegacyRegistry.localLabel("Fallback").equals(nativeName),"LocalUUID chooses canonical label");
            denied(()->LegacyIdentity.prepareRemote(new Login(),protocol),"Registry presence must not grant remote trust");
            Manager manager=new Manager();manager.field_2708.add(new Player(nativeName));
            check(LegacyIdentity.resolveAlias(manager,display).equals(nativeName),"Unique online command alias resolves");
            check(LegacyIdentity.completionNames(new String[]{nativeName})[0].equals(nativeName),"Historical multi-token names keep a usable native command token");
            denied(()->LegacyIdentity.rejectDuplicate(manager,nativeName),"Same account duplicate must not kick existing player");
            check(manager.field_2708.size()==1,"Duplicate check had no disconnect side effect");
            String second=LegacyRegistry.canonicalName(2),sameLabel=Base64.getEncoder().encodeToString("Shared".getBytes(StandardCharsets.UTF_8));
            String rows="1|"+nativeName+"|"+sameLabel+"|"+uuid+"\n2|"+second+"|"+sameLabel+"|"+UUID.randomUUID()+"\n";
            Files.writeString(registry,rows,StandardCharsets.UTF_8);Files.setLastModifiedTime(registry,java.nio.file.attribute.FileTime.fromMillis(System.currentTimeMillis()+2000));
            manager.field_2708.add(new Player(second));
            check(LegacyIdentity.resolveAlias(manager,"Shared").equals("Shared"),"Ambiguous alias does not select either actor");
            check(Arrays.equals(LegacyIdentity.completionNames(new String[]{nativeName,second}),new String[]{nativeName,second}),"Ambiguous completion keeps distinct native tokens");
            check(LegacyIdentity.resolveAlias(manager,second).equals(second),"Explicit native token still selects its own actor");
            rows="1|"+nativeName+"|"+sameLabel+"|"+uuid+"\n1|"+nativeName+"|"+sameLabel+"|"+UUID.randomUUID()+"\n3|"+LegacyRegistry.canonicalName(3)+"|/w==|"+UUID.randomUUID()+"\n";
            Files.writeString(registry,rows,StandardCharsets.UTF_8);Files.setLastModifiedTime(registry,java.nio.file.attribute.FileTime.fromMillis(System.currentTimeMillis()+4000));
            check(LegacyRegistry.entry(nativeName)==null,"Conflicting local owner rows are not guessed");
            check(LegacyRegistry.entry(LegacyRegistry.canonicalName(3))==null,"Malformed UTF8 labels are rejected");
            check(LegacyRegistry.localLabel("Fallback").equals("Fallback"),"Ambiguous local mapping does not assign another profile");
        }finally{Files.deleteIfExists(registry);Files.deleteIfExists(directory);}
        System.out.println("LegacyPortPolicyTest PASS "+assertions+" assertions; Steam authenticated gameplay NOT RUN");
    }
}
