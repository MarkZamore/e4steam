package link.e4steam.legacy164;

import java.lang.reflect.*;

/** Exact intermediary symbols for the declared 1.6.4 platform, no name guessing. */
public final class R {
    private R() {}
    public static Class<?> type(String name) {
        try { return Class.forName(name, true, R.class.getClassLoader()); }
        catch (ReflectiveOperationException e) { throw new IllegalStateException(name, e); }
    }
    public static Object get(Object owner, String name) {
        try { return field(owner instanceof Class<?> ? (Class<?>) owner : owner.getClass(),name).get(owner instanceof Class<?> ? null : owner); }
        catch (ReflectiveOperationException e) { throw new IllegalStateException(name,e); }
    }
    public static void set(Object owner, String name, Object value) {
        try { field(owner.getClass(),name).set(owner,value); }
        catch (ReflectiveOperationException e) { throw new IllegalStateException(name,e); }
    }
    private static Field field(Class<?> type,String name) throws NoSuchFieldException {
        for(Class<?> c=type;c!=null;c=c.getSuperclass()) try { Field f=c.getDeclaredField(name); f.setAccessible(true); return f; } catch(NoSuchFieldException ignored) {}
        throw new NoSuchFieldException(type.getName()+'.'+name);
    }
    private static boolean accepts(Class<?>[] types,Object[] values) {
        if(types.length!=values.length)return false;
        for(int i=0;i<types.length;i++) {
            Class<?> t=types[i]; Object v=values[i];
            if(v==null){if(t.isPrimitive())return false;continue;}
            if(t.isPrimitive())t=t==int.class?Integer.class:t==boolean.class?Boolean.class:t==long.class?Long.class:t==float.class?Float.class:t==double.class?Double.class:t;
            if(!t.isInstance(v))return false;
        }
        return true;
    }
    public static Object call(Object owner,String name,Object...args) {
        Class<?> type=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();
        for(Class<?> c=type;c!=null;c=c.getSuperclass()) for(Method m:c.getDeclaredMethods()) {
            if(m.getName().equals(name)&&accepts(m.getParameterTypes(),args))try {m.setAccessible(true);return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(ReflectiveOperationException e){throw failure(name,e);}
        }
        throw new IllegalStateException("Missing native method "+type.getName()+'.'+name);
    }
    public static Object create(String name,Object...args) {
        for(Constructor<?> c:type(name).getDeclaredConstructors()) if(accepts(c.getParameterTypes(),args))try {c.setAccessible(true);return c.newInstance(args);}catch(ReflectiveOperationException e){throw failure(name,e);}
        throw new IllegalStateException("Missing native constructor "+name);
    }
    private static IllegalStateException failure(String site,ReflectiveOperationException e){return new IllegalStateException(site,e instanceof InvocationTargetException?((InvocationTargetException)e).getCause():e);}
    public static Object minecraft(){return call(type("net.minecraft.class_1600"),"method_2965");}
}
