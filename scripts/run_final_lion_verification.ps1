param(
    [switch]$MasterOnly,
    [switch]$GlbOnly,
    [switch]$Draco,
    [string]$BlenderBinary = $env:LION_BLENDER
)

$ErrorActionPreference = 'Stop'
if ($MasterOnly -and $GlbOnly) { throw 'Choose one mode, or neither for both.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BlenderBinary) {
    if (Test-Path -LiteralPath 'F:\Blender\blender.exe' -PathType Leaf) {
        $BlenderBinary = 'F:\Blender\blender.exe'
    } else {
        $BlenderBinary = (Get-Command blender -ErrorAction Stop).Source
    }
}
if (-not (Test-Path -LiteralPath $BlenderBinary -PathType Leaf)) {
    throw 'Set LION_BLENDER or -BlenderBinary to the Blender executable.'
}
$blenderBinary = (Resolve-Path -LiteralPath $BlenderBinary).Path
$verifyScript = Join-Path $PSScriptRoot 'verify_final_lion.py'

# Run only after the final writer has finished saving its artifact.
# Each mode reopens the real file in a separate factory-startup process.
if (-not $GlbOnly) {
    & $blenderBinary --background --factory-startup --python-exit-code 1 --python $verifyScript -- --master --dual-source --root $projectRoot
    if ($LASTEXITCODE -ne 0) { throw 'Native master QA failed; inspect docs/final_master_verification.json.' }
}

if (-not $MasterOnly) {
    & $blenderBinary --background --factory-startup --python-exit-code 1 --python $verifyScript -- --glb --dual-source --root $projectRoot
    if ($LASTEXITCODE -ne 0) { throw 'GLB QA failed; inspect docs/final_glb_verification.json.' }
}

if ($Draco) {
    $dracoScript = Join-Path $PSScriptRoot 'verify_draco_lion.py'
    & $blenderBinary --background --factory-startup --python-exit-code 1 --python $dracoScript -- --root $projectRoot
    if ($LASTEXITCODE -ne 0) { throw 'Draco GLB QA failed; inspect docs/final_draco_verification.json.' }
}
