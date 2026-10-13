param(
    [Parameter(Position = 0)][string]$BlenderBinary = $env:LION_BLENDER,
    [Parameter(Position = 1)][string]$OutputPath,
    [switch]$Force,
    [switch]$NoLfsPull,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
# Codex can launch this Windows PowerShell entry point from a PowerShell 7 host.
# Prefer this runtime's built-in modules over an inherited PSModulePath.
$builtinModuleRoot = Join-Path $PSHOME 'Modules'
$env:PSModulePath = $builtinModuleRoot + [IO.Path]::PathSeparator + $env:PSModulePath
Import-Module (Join-Path $builtinModuleRoot 'Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $builtinModuleRoot 'Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1') -ErrorAction Stop
function Get-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}
if ($Help) {
    Write-Output 'build_model.cmd "F:\Blender\blender.exe" [output.blend] [-Force] [-NoLfsPull]'
    Write-Output 'Requires Windows PowerShell, Blender 5.0.x and hydrated build inputs. No external Python or cloud service.'
    Write-Output 'Default output: blender/Lion_Final_Master.blend. Existing output is preserved unless -Force; replacements keep a backup.'
    exit 0
}
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $BlenderBinary) {
    if (Test-Path -LiteralPath 'F:\Blender\blender.exe' -PathType Leaf) { $BlenderBinary = 'F:\Blender\blender.exe' }
    else { $BlenderBinary = (Get-Command blender -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath $BlenderBinary -PathType Leaf)) { throw 'Set LION_BLENDER or supply the actual Blender executable.' }
$BlenderBinary = (Resolve-Path -LiteralPath $BlenderBinary).Path
if (-not $OutputPath) { $OutputPath = Join-Path $projectRoot 'blender\Lion_Final_Master.blend' }
elseif (-not [IO.Path]::IsPathRooted($OutputPath)) { $OutputPath = Join-Path $projectRoot $OutputPath }
$output = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($output) -ne '.blend') { throw 'Output must have the .blend extension.' }
if ((Test-Path -LiteralPath $output) -and -not $Force) { throw 'Output already exists and was preserved. Choose another output, or explicitly pass -Force.' }
$inputs = @(
    'blender/checkpoints/Lion_Body_Quality_Stage.blend',
    'blender/checkpoints/Lion_Head_Quality_Stage_v2.blend',
    'blender/checkpoints/Lion_Detailed_Parts.blend',
    'generated/Lux3D_Lion_Base_glb.glb',
    'generated/candidates/head_highdetail/Lion_head_highdetail_glb.glb',
    'textures/brocade_new/brocade_reference_synthesis.png',
    'textures/brocade_new/body_micro_weave_normal_2048.png',
    'docs/head_candidate_parts_report_v3.json',
    'docs/brocade_uv_study_clear_v2_reimport.json',
    'docs/trim_cloth_recovery_mask.npy',
    'docs/trim_cloth_recovery_source_ids.npy',
    'docs/trim_geometry_features.npz'
)
foreach ($relative in $inputs) {
    if ([IO.Path]::GetFullPath((Join-Path $projectRoot $relative)) -eq $output) { throw 'A build input cannot be used as the output.' }
}

function Test-LfsPointer([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $stream = [IO.File]::OpenRead($Path)
    try {
        $buffer = New-Object byte[] 128
        $count = $stream.Read($buffer, 0, $buffer.Length)
        return [Text.Encoding]::ASCII.GetString($buffer, 0, $count).StartsWith('version https://git-lfs.github.com/spec/v1')
    } finally { $stream.Dispose() }
}
function Get-MissingInputs {
    @($inputs | Where-Object {
        $candidate = Join-Path $projectRoot $_
        -not (Test-Path -LiteralPath $candidate -PathType Leaf) -or (Test-LfsPointer $candidate)
    })
}
$missing = @(Get-MissingInputs)
if ($missing.Count -gt 0 -and -not $NoLfsPull) {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCommand -and (Test-Path -LiteralPath (Join-Path $projectRoot '.git'))) {
        Write-Output 'Fetching only required build inputs with Git LFS...'
        $nativeErrorPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $gitCommand.Source -C $projectRoot lfs pull ("--include=" + ($inputs -join ',')) '--exclude='
            $lfsExitCode = $LASTEXITCODE
        } finally { $ErrorActionPreference = $nativeErrorPreference }
        if ($lfsExitCode -ne 0) { throw 'Targeted git lfs pull failed. Resolve repository access/LFS availability and retry.' }
    }
    $missing = @(Get-MissingInputs)
}
if ($missing.Count -gt 0) { throw ('Required build inputs are missing or still LFS pointers: ' + ($missing -join ', ')) }
$scriptNames = @(
    'project_paths.py', 'build_native_model.py', 'refine_lion_master.py',
    'assemble_quality_revision.py', 'correct_quality_material_boundaries.py',
    'finalize_quality_revision.py', 'apply_final_head_detail.py',
    'fiber_tools.py', 'lion_material_tools.py', 'study_brocade_cylinder.py',
    'study_head_forehead_brocade.py', 'recover_trim_cloth.py',
    'probe_trim_cloth_recovery.py', 'add_fitted_details.py', 'verify_final_lion.py'
)
$scripts = @($scriptNames | ForEach-Object { Get-Item -LiteralPath (Join-Path $PSScriptRoot $_) })
foreach ($script in $scripts) { if (Test-LfsPointer $script.FullName) { throw ('Python script is an unhydrated LFS pointer: ' + $script.Name) } }
$cacheRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'cache\builds'))
foreach ($directory in @($projectRoot, (Join-Path $projectRoot 'cache'), $cacheRoot)) {
    if ((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Build staging parents must be ordinary directories, not reparse links.'
    }
}
$runName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$runDir = [IO.Path]::GetFullPath((Join-Path $cacheRoot $runName))
$stageRoot = [IO.Path]::GetFullPath((Join-Path $runDir 'staging'))
if (-not $stageRoot.StartsWith($cacheRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Staging directory escaped the project cache.' }
[void][IO.Directory]::CreateDirectory($stageRoot)
$resultPath = Join-Path $runDir 'build_result.json'
$started = [DateTime]::UtcNow
$records = @()
$stageTimings = @()
$build = [ordered]@{ schema='lion-project.native-build/v1'; status='running'; started_at_utc=$started.ToString('o'); project=$projectRoot; output=$output; blender=$BlenderBinary; input_files=@(); stage_timings=@(); published=$false }
function Save-BuildResult { $build | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $resultPath -Encoding UTF8 }
function Run-Blender([string]$Label, [string]$Script, [string[]]$Arguments) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $log = Join-Path $runDir ($Label + '.log')
    Write-Output ("Running " + $Label + "...")
    $nativeErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $BlenderBinary --background --factory-startup --python-exit-code 1 --python $Script -- @Arguments *> $log
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $nativeErrorPreference }
    $clock.Stop()
    $script:stageTimings += [pscustomobject]@{ phase=$Label; seconds=$clock.Elapsed.TotalSeconds; exit_code=$code; log=$log }
    if ($code -ne 0) {
        Get-Content -LiteralPath $log -Tail 25 | Write-Output
        throw ("Blender phase failed: " + $Label + ". Full log: " + $log)
    }
}
try {
    foreach ($relative in $inputs) {
        $source = Join-Path $projectRoot $relative
        $destination = Join-Path $stageRoot $relative
        [void][IO.Directory]::CreateDirectory((Split-Path -Parent $destination))
        $hash = Get-Sha256 $source
        Copy-Item -LiteralPath $source -Destination $destination
        $records += [pscustomobject]@{ path=$relative; bytes=(Get-Item -LiteralPath $source).Length; sha256=$hash }
    }
    $stageScripts = Join-Path $stageRoot 'scripts'
    [void][IO.Directory]::CreateDirectory($stageScripts)
    foreach ($script in $scripts) {
        Copy-Item -LiteralPath $script.FullName -Destination (Join-Path $stageScripts $script.Name)
        $records += [pscustomobject]@{ path=('scripts/' + $script.Name); bytes=$script.Length; sha256=(Get-Sha256 $script.FullName) }
    }
    foreach ($relative in @('build_model.cmd', 'scripts/build_model.ps1')) {
        $recipe = Join-Path $projectRoot $relative
        $records += [pscustomobject]@{ path=$relative; bytes=(Get-Item -LiteralPath $recipe).Length; sha256=(Get-Sha256 $recipe) }
    }
    $build['input_files'] = $records
    Save-BuildResult
    $constructReport = Join-Path $runDir 'construction.json'
    Run-Blender 'construct' (Join-Path $stageScripts 'build_native_model.py') @('--source-project',$projectRoot,'--target',$output,'--result',$constructReport)
    $stageMaster = Join-Path $stageRoot 'blender\Lion_Final_Master.blend'
    $stagedQa = Join-Path $runDir 'staged_native_verification.json'
    Run-Blender 'verify_staged' (Join-Path $stageScripts 'verify_final_lion.py') @('--master','--dual-source','--root',$stageRoot,'--input',$stageMaster,'--report',$stagedQa)
    $qa = Get-Content -LiteralPath $stagedQa -Raw | ConvertFrom-Json
    if ($qa.status -ne 'pass' -or $qa.errors.Count -gt 0 -or $qa.native_fiber_strand_count -ne 980957 -or $qa.source_part_count -ne 20 -or $qa.asset_object_count -ne 256) {
        throw 'Reconstructed native model did not pass the accepted structural/count gates.'
    }
    foreach ($record in $records) {
        if ((Get-Sha256 (Join-Path $projectRoot $record.path)) -ne $record.sha256) { throw ('Original input changed during isolated build: ' + $record.path) }
    }
    $nativeHash = Get-Sha256 $stageMaster
    $outputDir = Split-Path -Parent $output
    [void][IO.Directory]::CreateDirectory($outputDir)
    $temporaryOutput = $output + '.' + $runName + '.partial'
    Copy-Item -LiteralPath $stageMaster -Destination $temporaryOutput
    if (Test-Path -LiteralPath $output) {
        if (-not $Force) { throw 'Output appeared during the build and was preserved.' }
        $backup = $output + '.before-build-' + $runName + '.blend'
        [IO.File]::Replace($temporaryOutput, $output, $backup)
        $build['backup'] = $backup
    } else { [IO.File]::Move($temporaryOutput, $output) }
    if ((Get-Sha256 $output) -ne $nativeHash) { throw 'Published model hash differs from the verified staged model.' }
    $build['published'] = $true
    # Removal is restricted to this unique, checked staging path. A second fresh
    # process verifies the real output after staging has gone away.
    if (-not $stageRoot.StartsWith($runDir + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $stageRoot -eq $projectRoot) { throw 'Unsafe staging cleanup path.' }
    $reparseEntries = @(Get-ChildItem -LiteralPath $stageRoot -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if (((Get-Item -LiteralPath $stageRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -or $reparseEntries.Count -gt 0) {
        throw 'Staging contains an unexpected reparse link; refusing recursive cleanup.'
    }
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
    $finalQa = Join-Path $runDir 'native_verification.json'
    Run-Blender 'verify_published' (Join-Path $PSScriptRoot 'verify_final_lion.py') @('--master','--dual-source','--root',$projectRoot,'--input',$output,'--report',$finalQa)
    $publishedQa = Get-Content -LiteralPath $finalQa -Raw | ConvertFrom-Json
    if ($publishedQa.status -ne 'pass' -or $publishedQa.errors.Count -gt 0 -or $publishedQa.input.sha256_after -ne $nativeHash) { throw 'Published output verification failed.' }
    $build['status'] = 'pass'
    $build['output_sha256'] = $nativeHash
    $build['output_bytes'] = (Get-Item -LiteralPath $output).Length
    $build['construction_report'] = $constructReport
    $build['native_verification'] = $finalQa
    $build['staging_removed'] = -not (Test-Path -LiteralPath $stageRoot)
    $build['native_fiber_strands'] = $publishedQa.native_fiber_strand_count
    $build['source_parts'] = $publishedQa.source_part_count
    $build['asset_objects'] = $publishedQa.asset_object_count
    $build['completed_at_utc'] = [DateTime]::UtcNow.ToString('o')
    $build['elapsed_seconds'] = ([DateTime]::UtcNow - $started).TotalSeconds
    $build['stage_timings'] = $stageTimings
    Save-BuildResult
    Write-Output ("Native model built and verified: " + $output)
    Write-Output ("Build evidence: " + $resultPath)
} catch {
    $build['status'] = 'fail'
    $build['error'] = $_.Exception.Message
    $build['stage_timings'] = $stageTimings
    $build['completed_at_utc'] = [DateTime]::UtcNow.ToString('o')
    Save-BuildResult
    Write-Error $_
    exit 1
}
