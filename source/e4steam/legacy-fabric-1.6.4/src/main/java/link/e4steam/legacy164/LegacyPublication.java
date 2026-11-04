package link.e4steam.legacy164;

import link.e4steam.steam.SteamRuntime;
import java.util.*;
import java.util.concurrent.*;

/** Native world/client capture and generation-bound Steam description writes. */
public final class LegacyPublication {
    public static final String PLAYER_KEY="lanminecraft_player",WORLD_KEY="lanminecraft_world",DISPLAY_KEY="lanminecraft_display";
    private static final Map<Object,Publication> PUBLICATIONS=Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<Object,ConcurrentLinkedQueue<Runnable>> SERVER_TASKS=Collections.synchronizedMap(new WeakHashMap<>());
    private LegacyPublication(){}
    public static void tick(Object server){ConcurrentLinkedQueue<Runnable> tasks=SERVER_TASKS.get(server);if(tasks!=null){Runnable task;while((task=tasks.poll())!=null)task.run();}}
    public static void closed(Object server){Publication p=PUBLICATIONS.remove(server);if(p!=null)p.active=false;SERVER_TASKS.remove(server);}
    public static void published(Object minecraft,Object server,int port){
        synchronized(PUBLICATIONS){if(PUBLICATIONS.containsKey(server))return;Publication p=new Publication(minecraft,server,port);PUBLICATIONS.put(server,p);Thread worker=new Thread(p,"e4steam-legacy-world-description");worker.setDaemon(true);worker.start();}
    }
    private static <T> CompletableFuture<T> client(Callable<T> action){CompletableFuture<T> future=new CompletableFuture<>();Legacy164Client.submit(()->{try{future.complete(action.call());}catch(Throwable failure){future.completeExceptionally(failure);}});return future;}
    private static <T> CompletableFuture<T> server(Object server,Callable<T> action){CompletableFuture<T> future=new CompletableFuture<>();SERVER_TASKS.computeIfAbsent(server,key->new ConcurrentLinkedQueue<>()).add(()->{try{future.complete(action.call());}catch(Throwable failure){future.completeExceptionally(failure);}});return future;}
    @SuppressWarnings("unchecked") private static <T> CompletableFuture<T> steam(SteamRuntime runtime,Callable<T> action){return (CompletableFuture<T>)R.call(runtime,"submitSteamTask",action);}
    public static String cleanName(String name){
        if(name==null)return "";String clean=name.replaceAll("[\\p{Cc}\\p{Cf}§]","").trim();
        return clean.substring(0,clean.offsetByCodePoints(0,Math.min(64,clean.codePointCount(0,clean.length()))));
    }
    private static final class Publication implements Runnable {
        final Object minecraft,server;final int port;volatile boolean active=true;
        Publication(Object minecraft,Object server,int port){this.minecraft=minecraft;this.server=server;this.port=port;}
        boolean current(){return active&&R.call(minecraft,"method_2909")==server;}
        @Override public void run(){
            try {
                String player=client(()->current()?cleanName(LegacyIdentity.hostDisplayName(server)):null).get(8,TimeUnit.SECONDS);
                if(player==null||player.isEmpty())return;
                String world=server(server,()->{
                    Object[] worlds=(Object[])R.get(server,"field_3850");
                    if(!active||worlds==null||worlds.length==0||worlds[0]==null)return null;
                    return cleanName((String)R.call(R.call(worlds[0],"method_3588"),"method_226"));
                }).get(8,TimeUnit.SECONDS);
                if(world==null||world.isEmpty())return;
                SteamRuntime runtime=SteamRuntime.get();runtime.awaitReady();long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                while(active&&System.nanoTime()<deadline){
                    Object owner=steam(runtime,()->{Object host=R.get(runtime,"hostRegistration");return host!=null&&((Integer)R.call(host,"localPort"))==port?R.call(host,"owner"):null;}).get(8,TimeUnit.SECONDS);
                    if(!client(this::current).get(8,TimeUnit.SECONDS))return;
                    if(owner!=null&&steam(runtime,()->{
                        Object host=R.get(runtime,"hostRegistration"),social=R.get(runtime,"lobbyManager");
                        if(!active||host==null||R.call(host,"owner")!=owner||social==null||R.get(social,"hostLobbyOwner")!=owner)return false;
                        long lobbyId=(Long)R.get(social,"hostLobbyId");if(lobbyId==0)return false;
                        Object lobby=R.call(R.type("com.codedisaster.steamworks.SteamID"),"createFromNativeHandle",lobbyId),matchmaking=R.get(social,"matchmaking");
                        if(!Boolean.TRUE.equals(R.call(matchmaking,"setLobbyData",lobby,DISPLAY_KEY,"0")))return false;
                        return Boolean.TRUE.equals(R.call(matchmaking,"setLobbyData",lobby,PLAYER_KEY,player))&&Boolean.TRUE.equals(R.call(matchmaking,"setLobbyData",lobby,WORLD_KEY,world))&&Boolean.TRUE.equals(R.call(matchmaking,"setLobbyData",lobby,DISPLAY_KEY,"1"));
                    }).get(8,TimeUnit.SECONDS))return;
                    Thread.sleep(500);
                }
                if(active)throw new TimeoutException("Steam host lobby description was not ready");
            }catch(Exception failure){if(active)System.err.println("[e4steam Legacy164] Could not publish the native world description: "+failure.getClass().getSimpleName());}
        }
    }
}
