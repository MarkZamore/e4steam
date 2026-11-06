#Requires -Version 7.2
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
if ($env:STEAM_SDK_LOCATION) {
    throw 'Unset STEAM_SDK_LOCATION to use the locked Steam SDK.'
}
$metadataText = & cargo metadata --locked --format-version 1 --manifest-path (Join-Path $PSScriptRoot 'Cargo.toml')
if ($LASTEXITCODE -ne 0) {
    throw 'Could not resolve the locked native Steam dependencies.'
}
$metadata = $metadataText | Out-String | ConvertFrom-Json
$sdk = @($metadata.packages | Where-Object {
    $_.name -eq 'steamworks-sys' -and $_.version -eq '0.13.0' -and
    $_.source -eq 'registry+https://github.com/rust-lang/crates.io-index'
})
if ($sdk.Count -ne 1) {
    throw 'The resolved Steam SDK does not match the locked dependency.'
}
$dllPath = Join-Path (Split-Path -Parent $sdk[0].manifest_path) 'lib/steam/redistributable_bin/win64/steam_api64.dll'
$dll = Get-Item -LiteralPath $dllPath
if ($dll.Length -ne 317080 -or
    (Get-FileHash -LiteralPath $dll.FullName -Algorithm SHA256).Hash -ne
    'EB17909A76668CF9AE0B92A618A34A50F6C73D3A6787CB4DD8CE36A8B10BFB75') {
    throw 'The Steam SDK DLL size or SHA256 differs from the reviewed input.'
}
$signature = Get-AuthenticodeSignature -LiteralPath $dll.FullName
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|, )CN=Valve Corp\.(,|$)') {
    throw 'The reviewed Valve signature on the Steam SDK DLL is invalid.'
}
$dll.FullName
