# Example from the LANMinecraft workspace:
# .\LocalSources\e4steam-forge112-login-fix\tools\Test-Forge112LoginOrder.ps1 -LauncherRoot .\Minecraft\Launcher -RunDirectory .\artifacts\agent-runs\forge112-login-20261116
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$LauncherRoot,
    [Parameter(Mandatory)][string]$RunDirectory
)

$ErrorActionPreference = 'Stop'
$launcher = (Resolve-Path -LiteralPath $LauncherRoot).Path
$run = Get-Item -LiteralPath (Resolve-Path -LiteralPath $RunDirectory).Path
if ($run.Parent.Name -ne 'agent-runs' -or
    ($run.Parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    ($run.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    -not (Test-Path -LiteralPath (Join-Path $run.FullName 'RUN.json') -PathType Leaf)) {
    throw 'Point RunDirectory to an ordinary, task-owned agent-runs directory with RUN.json.'
}

$java8 = Join-Path $launcher 'JavaRuntimes/runtime/windows-x64/java-8/bin'
$shared = Join-Path $launcher 'Shared'
$vanilla = Join-Path $shared 'versions/1.12.2/1.12.2.jar'
$forge = Join-Path $shared 'libraries/net/minecraftforge/forge/1.12.2-14.23.5.2859/forge-1.12.2-14.23.5.2859.jar'
$expectedVanillaHash = '8ADA07DA5EE77DAD3527BD7278FBD05EE1FC8A597813B216A871A2D7D64CC64F'
$expectedForgeHash = 'BD8314729D787E35164476D75AFB337AFB9783917E4F6FA1F77F049ADBA22F2D'
if ((Get-FileHash -LiteralPath $vanilla).Hash -ne $expectedVanillaHash -or
    (Get-FileHash -LiteralPath $forge).Hash -ne $expectedForgeHash) {
    throw 'Expected installed Minecraft 1.12.2 and Forge 14.23.5.2859 inputs.'
}

# Forge and vanilla are loaded in the probe's isolated class loader. Keep the
# Log4j API only so the game XML cannot open a rolling game log during this test.
$relativeLibraries = @(
    'io/netty/netty-all/4.1.9.Final/netty-all-4.1.9.Final.jar'
    'org/apache/logging/log4j/log4j-api/2.15.0/log4j-api-2.15.0.jar'
    'net/minecraft/launchwrapper/1.12/launchwrapper-1.12.jar'
    'org/ow2/asm/asm-debug-all/5.2/asm-debug-all-5.2.jar'
    'lzma/lzma/0.0.1/lzma-0.0.1.jar'
    'commons-io/commons-io/2.5/commons-io-2.5.jar'
    'com/google/guava/guava/21.0/guava-21.0.jar'
    'com/google/code/gson/gson/2.8.0/gson-2.8.0.jar'
    'com/mojang/authlib/1.5.25/authlib-1.5.25.jar'
    'org/apache/commons/commons-lang3/3.5/commons-lang3-3.5.jar'
    'it/unimi/dsi/fastutil/7.1.0/fastutil-7.1.0.jar'
    'com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar'
)
$libraryRoot = Join-Path $shared 'libraries'
$libraries = $relativeLibraries | ForEach-Object { (Resolve-Path -LiteralPath (Join-Path $libraryRoot $_)).Path }
$classpath = $libraries -join [IO.Path]::PathSeparator
$probe = Join-Path $PSScriptRoot 'Forge112LoginOrderProbe.java'
$helper = Join-Path $PSScriptRoot '../source/e4steam/retro/forge-1.12.2/src/main/java/link/e4steam/retro/forge/Forge112LoginHandshake.java'
$classes = New-Item -ItemType Directory -Path (Join-Path $run.FullName ('login-order-classes-' + [Guid]::NewGuid().ToString('N')))
try {
    & (Join-Path $java8 'javac.exe') -encoding UTF-8 -d $classes.FullName -cp $classpath $probe $helper
    if ($LASTEXITCODE -ne 0) { throw 'Login-order probe compilation failed.' }
    $probeClasspath = $classes.FullName + [IO.Path]::PathSeparator + $classpath
    & (Join-Path $java8 'java.exe') '-Dlog4j2.loggerContextFactory=org.apache.logging.log4j.simple.SimpleLoggerContextFactory' `
        -classpath $probeClasspath Forge112LoginOrderProbe $vanilla $forge
    if ($LASTEXITCODE -ne 0) { throw 'Login-order probe failed.' }
} finally {
    $resolved = Get-Item -LiteralPath (Resolve-Path -LiteralPath $classes.FullName).Path
    if ($resolved.Parent.FullName -ne $run.FullName -or
        ($resolved.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Unexpected path for compiled probe. Leaving it untouched.'
    }
    Remove-Item -LiteralPath $resolved.FullName -Recurse -Force
}
