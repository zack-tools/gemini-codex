---
name: chatgpt-portable-updater
description: Update ChatGPT or OpenAI Codex Windows desktop application in a portable, clean, and uninstalled manner. Use this skill when the user asks to update, download, or refresh ChatGPT/Codex without registering it into Windows Installed Apps or AppxPackage list.
---

# ChatGPT / Codex Portable Updater

## Overview

This skill allows Antigravity to check for, download, extract, and maintain portable versions of the ChatGPT Windows desktop client (`OpenAI.Codex`) without installing it into Windows (`Add-AppxPackage` or Windows Store installer). It guarantees that no entries are created in the Windows "Installed apps" settings or registry uninstall lists.

## Architecture & Workflows

1. **Query Latest Official Package**:
   * Uses Microsoft Store Product ID `9PLM9XGG6VKS`.
   * Queries Microsoft Store Catalog & Windows Update SOAP FE3 endpoints directly from Microsoft CDN (`*.delivery.mp.microsoft.com`).
   * No third-party mirror site dependencies, authentic SHA1 verification.

2. **Zero-Install Extraction**:
   * Downloads official `.msix` directly to `%USERPROFILE%\Downloads\`.
   * Extracts static application payload into target directory (e.g., `<TargetParentDir>\OpenAI.Codex_<version>_x64__2p2nqsd0c76g0`) using `7z.exe`.
   * Never invokes `Add-AppxPackage` or system package registers.

3. **Shortcut Redirection**:
   * Inspects and updates Desktop shortcuts (`ChatGPT - 捷徑.lnk`, `Codex - 捷徑.lnk`) to target the latest executable:
     * `...\app\ChatGPT.exe`
     * `...\app\Codex.exe`

## How to Run

### Via PowerShell Helper
From the repository root or skill directory:

```powershell
.\Update-ChatGPT-Portable.ps1
# 或從本 skill 目錄：
.\scripts\Update-ChatGPT-Portable.ps1 -TargetParentDir "D:\"
```

Parameters:
* `-TargetParentDir` : Location to extract portable app version folders (defaults to `D:\` or custom directory).
* `-Force` : Forces re-download and re-extraction even if the latest version directory already exists.

### Via Batch File
Double-click or run from command prompt:
```cmd
Update-ChatGPT-Portable.bat
```

## Verification

To verify that the application has zero installation footprints in Windows:

```powershell
Get-AppxPackage -Name "*OpenAI.Codex*"
Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object { $_.DisplayName -match "ChatGPT|Codex" }
```
Both queries should return 0 results.

