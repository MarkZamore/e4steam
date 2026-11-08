"""Reproduce the explicit source-built Legacy Fabric 1.6.4 Steam port.

The nineteen existing payloads are never rebuilt or rewritten by this command.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source/e4steam'
MODULE=SOURCE/'legacy-fabric-1.6.4'
UPSTREAM='bdcea00e30ca519fa8190c0c5c04785d42b31dbc'
RELEASE_REVISION=4
TAG=f'legacy-fabric-164-v{RELEASE_REVISION}'
IMPLEMENTATION_VERSION=f'0.3.4-lf164.{RELEASE_REVISION}'
NAME=f'e4steam-legacy-fabric-mc1.6.4-v{IMPLEMENTATION_VERSION}.jar'
DEPENDENCIES=[
 ('com.code-disaster.steamworks4j','steamworks4j','1.10.0','2da3d053f0405b6aeb68f94ab281f8eb827e7a9fc66230b7efb077be8aec2d64',True),
 ('com.code-disaster.steamworks4j','steamworks4j-server','1.10.0','7abdee44d0c53f07f9504de249fe9630da14797976e3d89941cd63bafd67adba',True),
 ('net.java.dev.jna','jna','5.10.0','e335c10679f743207d822c5f7948e930319835492575a9dba6b94f8a3b96fcc8',True),
 ('org.apache.logging.log4j','log4j-api','2.19.0','5ccb24ad9f92e768d0bc456d3061a737951262df803e004d2cad096b75a88d60',False),
 ('org.apache.logging.log4j','log4j-core','2.19.0','b4a1796fab7bfc36df015c1b4052459147997e8d215a7199d71d05f9e747e4f4',False),
 ('net.fabricmc','fabric-loader','0.18.2','3ab7f6b1732170394e77c9f31f8b598928f8766546f9849482431ddbd21f1acd',False),
 ('org.spongepowered','mixin','0.8.5','ca15a907e4d1f6b38cefed51d7df96a83347dcfb0bc8ced53111519e991d887d',False),
]

def sha(data):return hashlib.sha256(data).hexdigest()

def ordered_paths(paths):return sorted(paths,key=lambda path:path.relative_to(ROOT).as_posix())

def source_bytes(path):
    data=path.read_bytes()
    # Git's NOTICE input is LF; Windows autocrlf previously materialized it
    # differently. Pin the committed input and declare ZIP materialization.
    return data.replace(b'\r\n',b'\n') if path in {SOURCE/'NOTICE',SOURCE/'retro/core/build.gradle.kts'} else data

def dependency(row,cache):
    group,artifact,version,expected,_=row
    filename=f'{artifact}-{version}.jar'
    gradle=Path.home()/'.gradle/caches/modules-2/files-2.1'/group/artifact/version
    choices=list(gradle.glob('*/'+filename))+[cache/filename]
    extra=os.environ.get('E4STEAM_DEPENDENCIES','')
    if extra:choices.insert(0,Path(extra)/filename)
    for path in choices:
        if path.is_file() and sha(path.read_bytes())==expected:return path
    base='https://maven.fabricmc.net' if group=='net.fabricmc' else ('https://repo.spongepowered.org/repository/maven-public' if group=='org.spongepowered' else 'https://repo.maven.apache.org/maven2')
    url=f'{base}/{group.replace(".","/")}/{artifact}/{version}/{filename}'
    request=urllib.request.Request(url,headers={'User-Agent':'LANMinecraft-source-reproduction/1.0'})
    with urllib.request.urlopen(request,timeout=60) as response:data=response.read()
    if sha(data)!=expected:raise ValueError('Dependency SHA mismatch: '+filename)
    path=cache/filename;path.write_bytes(data);return path

def excluded(name):
    if name.endswith('/') or name.upper().startswith('META-INF/') and name.upper().endswith(('.SF','.RSA','.DSA')):return True
    if name=='META-INF/MANIFEST.MF' or name.startswith(('META-INF/versions/','META-INF/maven/','META-INF/native-image/')):return True
    if name.startswith('com/sun/jna/') and any(t in name for t in ('win32-x86/','win32-aarch64/','linux-x86/','linux-arm','linux-aarch64/','linux-ppc','linux-mips','linux-s390','linux-riscv','sunos-','freebsd-','openbsd-')):return True
    return name in {'steam_api.dll','steamworks4j.dll','steamworks4j-server.dll'} or 'encryptedappticket' in name

def build(output,java_home):
    javac=java_home/('bin/javac.exe' if os.name=='nt' else 'bin/javac')
    java=java_home/('bin/java.exe' if os.name=='nt' else 'bin/java')
    compiler=subprocess.check_output([str(javac),'-version'],text=True).strip()
    if compiler!='javac 25.0.2':raise ValueError('The frozen source port requires javac 25.0.2')
    output.mkdir(parents=True,exist_ok=True)
    cache=output/'deps';cache.mkdir(exist_ok=True)
    deps=[(row,dependency(row,cache)) for row in DEPENDENCIES]
    core=SOURCE/'retro/core'
    shared=re.findall(r'"(link/e4steam/[^"\n]+\.java)"',(core/'build.gradle.kts').read_text(encoding='utf-8'))
    shared+=['link/e4steam/steam/SteamReliableDataPacer.java','link/e4steam/steam/SteamAddonLobbyDirectory.java','link/e4steam/lan/LanSettings.java']
    sources=ordered_paths((core/'src/main/java').rglob('*.java'))+[SOURCE/'common/src/main/java'/name for name in shared]+ordered_paths((SOURCE/'api/src/main/java').rglob('*.java'))+ordered_paths((MODULE/'src/main/java').rglob('*.java'))
    classes=output/'classes'
    if classes.exists():
        if classes.resolve().parent!=output.resolve():raise ValueError('Unexpected build classes target')
        shutil.rmtree(classes)
    classes.mkdir()
    arguments=['--release','17','-encoding','UTF-8','-proc:none','-classpath',os.pathsep.join(str(path) for _,path in deps),'-d',str(classes)]+[str(path) for path in sources]
    argfile=output/'javac.args';argfile.write_text('\n'.join('"'+v.replace('\\','/')+'"' for v in arguments),encoding='utf-8',newline='\n')
    subprocess.run([str(javac),'@'+str(argfile)],check=True)
    entries={}
    for row,path in deps:
        if not row[4]:continue
        with zipfile.ZipFile(path) as jar:
            for name in jar.namelist():
                if not excluded(name):entries.setdefault(name,jar.read(name))
    for path in classes.rglob('*.class'):entries[path.relative_to(classes).as_posix()]=path.read_bytes()
    resources=ordered_paths(path for path in (MODULE/'src/main/resources').rglob('*') if path.is_file())
    for path in resources:entries[path.relative_to(MODULE/'src/main/resources').as_posix()]=path.read_bytes()
    entries['e4steam-version.properties']=b'version=0.3.4\n'
    entries['e4steam-retro.properties']=b'minecraftVersion=1.6.4\nminecraftBranch=1.6.4\n'
    # Mixin implementation classes must only be consumed by Mixin. Knot rejects
    # attempts to load them as ordinary runtime/preload helper classes.
    entries['e4steam-retro-preload.txt']=('\n'.join(sorted(name[:-6].replace('/','.') for name in entries if name.startswith('link/e4steam/') and name.endswith('.class') and '/mixin/' not in name))+'\n').encode()
    for source,target in [('LICENSE','META-INF/LICENSE-e4steam.txt'),('NOTICE','META-INF/NOTICE-e4steam.txt'),('THIRD_PARTY_NOTICES.md','META-INF/THIRD_PARTY_NOTICES.md')]:
        data=source_bytes(SOURCE/source)
        entries[target]=data.replace(b'\n',b'\r\n') if source=='NOTICE' else data
    entries['META-INF/MANIFEST.MF']=(
        'Manifest-Version: 1.0\nImplementation-Title: e4steam Legacy Fabric 1.6.4 port\n'
        f'Implementation-Version: {IMPLEMENTATION_VERSION}\n\n'
    ).encode('ascii')
    target=output/NAME
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as jar:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,11,4,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            info.create_system=0;info._compresslevel=6
            jar.writestr(info,data)
    tests=ordered_paths((MODULE/'src/test/java').rglob('*.java'))
    inputs=sources+tests+resources+[SOURCE/name for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md')]+[core/'build.gradle.kts']
    receipt={'schemaVersion':1,'type':'source-built-legacy-port','upstreamSourceCommit':UPSTREAM,'fileName':NAME,'sizeBytes':target.stat().st_size,'sha256':sha(target.read_bytes()),'recipeSha256':sha(Path(__file__).read_bytes()),'compiler':compiler,'sources':{path.relative_to(ROOT).as_posix():sha(source_bytes(path)) for path in inputs},'sourceTransforms':{'source/e4steam/NOTICE':'committed-LF-to-ZIP-CRLF','source/e4steam/retro/core/build.gradle.kts':'UTF8-universal-newlines-for-source-list'},'sourceBuiltClassSha256':{name:sha(data) for name,data in sorted(entries.items()) if name.endswith('.class') and name.startswith('link/e4steam/')},'dependencies':[{'group':row[0],'artifact':row[1],'version':row[2],'sha256':row[3],'bundled':row[4]} for row,_ in deps]}
    (output/'build-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    testclasses=output/'test-classes';testclasses.mkdir(exist_ok=True)
    testcp=os.pathsep.join([str(target),str(testclasses)]+[str(path) for row,path in deps if row[0]=='org.apache.logging.log4j'])
    subprocess.run([str(javac),'--release','17','-encoding','UTF-8','-proc:none','-classpath',testcp,'-d',str(testclasses),*[str(path) for path in tests]],check=True)
    subprocess.run([str(java),'-classpath',testcp,'link.e4steam.legacy164.LegacyPortPolicyTest'],check=True)
    print(json.dumps({key:receipt[key] for key in ('fileName','sizeBytes','sha256')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'dist'/TAG);parser.add_argument('--java-home',type=Path,default=Path(os.environ.get('JAVA_HOME','C:/Tools/jdk-25.0.2')))
    args=parser.parse_args();build(args.out.resolve(),args.java_home.resolve())
