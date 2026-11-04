package link.e4steam.legacy164;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Display/profile labels only. This registry never authenticates a connection. */
public final class LegacyRegistry {
    public record Entry(long steamId,String nativeName,String displayName,UUID uuid) {}
    private static volatile Map<String,Entry> entries=Map.of();
    private static volatile long modified=Long.MIN_VALUE;
    private LegacyRegistry() {}
    public static String canonicalName(long steamId) {
        if(steamId==0)throw new IllegalArgumentException("A Steam account is required");
        String base=Long.toUnsignedString(steamId,36);
        return "s"+"0".repeat(13-base.length())+base;
    }
    public static Entry entry(String name) { reload(); return entries.get(name); }
    public static String displayName(String name) {Entry e=entry(name);return e==null?name:e.displayName;}
    public static UUID uuid(String name){Entry e=entry(name);return e==null?null:e.uuid;}
    public static String localLabel(String original) {
        String local=System.getProperty("minecraft.portable.identity.localPlayer","");
        if(local.isEmpty())return original;
        reload();
        Entry found=null;
        for(Entry e:entries.values())if(e.uuid.toString().equals(local)) {if(found!=null)return original;found=e;}
        return found==null?original:found.nativeName;
    }
    private static synchronized void reload() {
        String configured=System.getProperty("minecraft.portable.legacy.registry","");
        if(configured.isEmpty())return;
        try {
            Path p=Path.of(configured);long stamp=Files.exists(p)?Files.getLastModifiedTime(p).toMillis():-1;
            if(stamp==modified)return;
            Map<String,Entry> read=new HashMap<>();Set<String> ambiguous=new HashSet<>();
            if(stamp>=0)for(String line:Files.readAllLines(p,StandardCharsets.UTF_8)) {
                String[] f=line.split("\\|",-1);
                if(f.length!=4)continue;
                try {
                    String display=StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(Base64.getDecoder().decode(f[2]))).toString();
                    if(display.isEmpty()||display.length()>16||display.codePoints().anyMatch(Character::isISOControl))continue;
                    long id=Long.parseUnsignedLong(f[0]);if(!canonicalName(id).equals(f[1]))continue;Entry e=new Entry(id,f[1],display,UUID.fromString(f[3]));Entry old=read.put(f[1],e);if(old!=null&&!old.equals(e))ambiguous.add(f[1]);
                }catch(IllegalArgumentException|java.nio.charset.CharacterCodingException ignored){}
            }
            ambiguous.forEach(read::remove);entries=Map.copyOf(read);modified=stamp;
        }catch(java.io.IOException e){throw new IllegalStateException("Legacy profile registry is unreadable",e);}
    }
}
