param(
    [string]$TargetParentDir = "D:\",
    [string]$ProductId = "9PLM9XGG6VKS",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     ChatGPT / OpenAI Codex Portable Updater              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check 7-Zip
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (-not (Test-Path $sevenZip)) {
    $cmd = Get-Command 7z, 7za -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $sevenZip = $cmd.Source }
    else {
        throw "7-Zip not found at C:\Program Files\7-Zip\7z.exe or in PATH."
    }
}
Write-Host "[1/4] 7-Zip detected: $sevenZip" -ForegroundColor Green

# 2. Download or locate MSIX using official Store query engine
$downloadsDir = Join-Path $env:USERPROFILE 'Downloads'
$enginePath = Join-Path $ScriptDir 'wingets.ps1'
if (-not (Test-Path $enginePath)) {
    $enginePath = "D:\Codex\wingets.ps1"
}
if (-not (Test-Path $enginePath)) {
    throw "Store query engine wingets.ps1 not found at $enginePath."
}

Write-Host "[2/4] Querying and downloading latest official package from Microsoft CDN..." -ForegroundColor Yellow
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $enginePath download $ProductId -d $downloadsDir

# Locate the downloaded MSIX file
$msixFiles = Get-ChildItem -Path $downloadsDir -Filter "*OpenAI.Codex*.msix" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
if (-not $msixFiles -or $msixFiles.Count -eq 0) {
    throw "No OpenAI.Codex MSIX package found in $downloadsDir."
}
$latestMsix = $msixFiles[0]

# Parse version and package name
# Format: OpenAI.Codex_<version>_x64__<pfn>_<guid>.msix or OpenAI.Codex_<version>_x64__<pfn>.msix
$fileName = $latestMsix.Name
if ($fileName -match "OpenAI\.Codex_([0-9\.]+)_x64__([0-9a-zA-Z]+)") {
    $version = $Matches[1]
    $pfn = $Matches[2]
} else {
    throw "Unrecognized MSIX filename format: $fileName"
}

$targetFolderName = "OpenAI.Codex_${version}_x64__${pfn}"
$targetExtractPath = Join-Path $TargetParentDir $targetFolderName

Write-Host "Latest Version: $version" -ForegroundColor Cyan
Write-Host "Target Directory: $targetExtractPath" -ForegroundColor Cyan

# 3. Extract payload
$chatgptExe = Join-Path $targetExtractPath "app\ChatGPT.exe"
$codexExe   = Join-Path $targetExtractPath "app\Codex.exe"

if ((Test-Path $chatgptExe) -and -not $Force) {
    Write-Host "`n[3/4] Version $version is already extracted and ready." -ForegroundColor Green
} else {
    Write-Host "`n[3/4] Extracting package payload using 7-Zip..." -ForegroundColor Yellow
    if (-not (Test-Path $targetExtractPath)) {
        New-Item -ItemType Directory -Path $targetExtractPath -Force | Out-Null
    }
    & $sevenZip x $latestMsix.FullName "-o$targetExtractPath" -y | Out-Null
    Write-Host "Extraction completed." -ForegroundColor Green
}

# 3.1 Fix URL-encoded scoped packages in cua_node (7-Zip extracts @ as %40, $ as %24)
$cuaModules = Join-Path $targetExtractPath "app\resources\cua_node\bin\node_modules"
if (Test-Path $cuaModules) {
    Write-Host "  -> Verifying and fixing CUA node_modules URL-encoded paths..." -ForegroundColor Cyan
    $mappings = @{
        "%40oai"     = "@oai"
        "%40img"     = "@img"
        "%40statsig" = "@statsig"
    }
    foreach ($k in $mappings.Keys) {
        $src = Join-Path $cuaModules $k
        $dst = Join-Path $cuaModules $mappings[$k]
        if ((Test-Path $src) -and (-not (Test-Path $dst))) {
            New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
        }
    }
    $statsigSrc = Join-Path $cuaModules "%40statsig\client-core\src"
    if (Test-Path $statsigSrc) {
        $encodedFiles = Get-ChildItem -Path $statsigSrc -Filter "%24*" -File
        foreach ($f in $encodedFiles) {
            $decodedName = $f.Name -replace "^%24", "$"
            $dstFile = Join-Path $statsigSrc $decodedName
            if (-not (Test-Path $dstFile)) {
                Copy-Item -Path $f.FullName -Destination $dstFile -Force
            }
        }
    }
}

# 4. Update Desktop Shortcuts
Write-Host "`n[4/4] Updating Desktop shortcuts to point to version $version..." -ForegroundColor Yellow
$sh = New-Object -ComObject WScript.Shell
$desktopShortcuts = Get-ChildItem -Path "$env:USERPROFILE\Desktop" -Filter "*.lnk" -ErrorAction SilentlyContinue

foreach ($s in $desktopShortcuts) {
    try {
        $sc = $sh.CreateShortcut($s.FullName)
        if ($sc.TargetPath -like "*ChatGPT.exe*" -or $s.Name -like "*ChatGPT*") {
            if (Test-Path $chatgptExe) {
                $sc.TargetPath = $chatgptExe
                $sc.WorkingDirectory = "$targetExtractPath\app"
                $sc.Save()
                Write-Host "  -> Updated shortcut: $($s.Name)" -ForegroundColor Green
            }
        } elseif ($sc.TargetPath -like "*Codex.exe*" -or $s.Name -like "*Codex*") {
            if (Test-Path $codexExe) {
                $sc.TargetPath = $codexExe
                $sc.WorkingDirectory = "$targetExtractPath\app"
                $sc.Save()
                Write-Host "  -> Updated shortcut: $($s.Name)" -ForegroundColor Green
            }
        }
    } catch {
        Write-Warning "Could not update shortcut: $($s.Name)"
    }
}

# Clean installation verification
$appx = Get-AppxPackage -Name "*OpenAI.Codex*" -ErrorAction SilentlyContinue
Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   Update completed successfully!" -ForegroundColor Green
Write-Host "   Active Version: $version" -ForegroundColor Green
Write-Host "   Executable: $chatgptExe" -ForegroundColor Green
Write-Host "   Windows Store Registered (Appx): $(@($appx).Count) items (Clean)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

