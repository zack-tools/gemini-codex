<#
.SYNOPSIS
    wingets — winget 风格的 Microsoft Store 离线安装包装器（纯 PowerShell）。

.DESCRIPTION
    对外提供与 winget 一致的"动词 + --参数"命令格式；脚本直接查询 Microsoft
    Store 与 Windows Update 官方接口获取 CDN 直链，安装走 Add-AppxPackage。
    无第三方 PowerShell 模块或第三方下载站点依赖，适用于 Store 应用损坏修复
    与离线分发场景。

    典型场景（修复损坏的 Store 应用包）：
        wingets install <productId> --force

.USAGE
    wingets install  <productId>  [--architecture x64] [--download-directory <dir>] [--force]
    wingets download <productId>  [--architecture x64] [--download-directory <dir>]
    wingets show    <productId>   [--channel Retail]
    wingets uninstall <已装包名>  [--force]
    wingets --help | --version

    参数与 winget 兼容：--id、-n/--name、-a/--architecture、-d/--download-directory、
    --channel、--force，以及为兼容而接受的 --accept-package-agreements、
    --accept-source-agreements、--silent、--verbose 等（忽略）。
#>

#Requires -Version 5.1
# 注意：不使用 [CmdletBinding()] + param —— 高级函数绑定器会把 -d 这类
# 以 - 开头的 token 当作参数名静默吞掉；$args 原始透传给自建解析器最可靠。
$Tokens = @($args)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'

# ── 常量 ──────────────────────────────────────────────────────
$script:DefaultOutDir = Join-Path $env:USERPROFILE 'Downloads\wingets'
$script:ValidVerbs    = @('install', 'download', 'show', 'search', 'uninstall')
$script:UnsupportedVerbs = @('upgrade', 'update', 'list', 'source', 'export', 'import', 'pin', 'configure', 'hash', 'validate', 'settings', 'features')
$script:IsChinese = [Globalization.CultureInfo]::CurrentUICulture.Name -like 'zh-*'

function Get-LocalizedText {
    param(
        [Parameter(Mandatory)][string]$Chinese,
        [Parameter(Mandatory)][string]$English
    )
    if ($script:IsChinese) { return $Chinese }
    return $English
}

# ── 帮助与版本 ────────────────────────────────────────────────
function Show-Help {
if (-not $script:IsChinese) {
@"
wingets — winget-style Microsoft Store offline installer (v1.2)

Usage: wingets <verb> <target> [<options>]

Verbs:
  install   Query and download packages, then install with Add-AppxPackage (default)
  download  Download packages without installing
  show      List available Store CDN packages for a product (same as search)
  search    Same as show; only a Store product ID is accepted
  uninstall Uninstall an installed Store app package

Options:
  -a, --architecture <x64|x86|arm|arm64|neutral|all>
                                             Target architecture (default: x64)
  -d, --download-directory <dir>           Download directory
  --channel <Retail>                       Store channel (verified Retail only)
  --force                                  install: uninstall existing package first;
                                           uninstall: skip confirmation
  --id <productId>                         Supply a Store product ID as an option
  -q, --query <productId>                  Product ID for search/show
  -n, --name <name>                        uninstall target; wildcards are accepted
  -s, --source <msstore>                   Compatible Store source selector
  --scope <user>                           Compatible current-user scope selector
  -v, --version                            Show the wingets version (when used alone)
  -h, --help                               Show this help

Accepted and ignored winget compatibility flags: -e/--exact,
  --accept-package-agreements, --accept-source-agreements, --silent,
  -i/--interactive, --verbose, --verbose-logs, --disable-interactivity,
  --ignore-warnings

Examples:
  wingets install 9PLM9XGG6VKS
  wingets install --id 9PLM9XGG6VKS -e --source msstore --scope user
  wingets install 9PLM9XGG6VKS --force
  wingets download 9PLM9XGG6VKS -a arm64 -d D:\pkg
  wingets show 9PLM9XGG6VKS
  wingets search -q 9PLM9XGG6VKS
  wingets uninstall OpenAI.Codex
"@
return
}
@"
wingets — winget 风格的 Microsoft Store 离线安装包装器 (v1.2)

用法: wingets <动词> <目标> [<选项>]

动词:
  install   查询并下载离线包，随后 Add-AppxPackage 安装（默认动词）
  download  仅下载离线包，不安装
  show      列出产品在商店 CDN 上的全部离线包（等同 search）
  search    同 show
  uninstall 卸载已安装的 Store 应用包

选项:
  -a, --architecture <x64|x86|arm|arm64|neutral|all>
                                             目标架构（默认 x64）
  -d, --download-directory <dir>           下载目录（默认 %USERPROFILE%\Downloads\wingets）
  --channel <Retail>                   商店通道（目前仅支持已验证的 Retail）
      --force                              install: 已装同名包时先卸载再装；uninstall: 免确认
      --id <productId>                     以选项形式提供产品 ID
  -q, --query <productId>                  search/show 的产品 ID
  -n, --name <名称>                        uninstall 的目标，支持通配符
  -s, --source <msstore>                   兼容的 Store 源选择
      --scope <user>                       兼容的当前用户范围选择
  -v, --version                            显示 wingets 版本
  -h, --help                               显示本帮助

兼容并忽略的 winget 参数: -e/--exact --accept-package-agreements
  --accept-source-agreements --silent -i/--interactive --verbose --verbose-logs
  --disable-interactivity --ignore-warnings

示例:
  wingets install 9PLM9XGG6VKS
  wingets install --id 9PLM9XGG6VKS -e --source msstore --scope user
  wingets install 9PLM9XGG6VKS --force          # 修复损坏包（先卸载后装）
  wingets download 9PLM9XGG6VKS -a arm64 -d D:\pkg
  wingets show 9PLM9XGG6VKS
  wingets uninstall OpenAI.Codex
"@
}

# ── 参数解析（winget 风格）───────────────────────────────────
function Parse-Arguments {
    $parsed = @{ Verb = $null; Target = $null; Arch = 'x64'; Out = $script:DefaultOutDir
                 Channel = 'Retail'; Force = $false; Id = $null; Name = $null
                 Source = $null; Scope = $null; Query = $null; PackageVersion = $null
                 NonInteractive = $false }
    if (@($Tokens).Count -eq 1 -and $Tokens[0] -match '^(--version|-v)$') {
        $parsed.Version = $true
        return $parsed
    }
    for ($i = 0; $i -lt @($Tokens).Count; $i++) {
        $t = $Tokens[$i]
        switch -Regex ($t) {
            '^(--help|-h|/\?|help)$'     { $parsed.Help = $true; continue }
            '^(--version|-v)$'           {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少版本值；查看脚本版本请单独运行 wingets --version" "$t requires a version value; run wingets --version by itself to show the script version") }
                $parsed.PackageVersion = $Tokens[++$i]; continue
            }
            '^(--id)$'                   {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText '--id 缺少产品 ID' '--id requires a product ID') }
                $parsed.Id = $Tokens[++$i]; continue
            }
            '^(-q|--query)$'              {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少查询值" "$t requires a query value") }
                $parsed.Query = $Tokens[++$i]; continue
            }
            '^(-n|--name)$'              {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少名称" "$t requires a name") }
                $parsed.Name = $Tokens[++$i]; continue
            }
            '^(-a|--architecture)$'      {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少架构值" "$t requires an architecture value") }
                $parsed.Arch = $Tokens[++$i]; continue
            }
            '^(-d|--download-directory)$'{
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少目录" "$t requires a directory") }
                $parsed.Out = $Tokens[++$i]; continue
            }
            '^(--channel)$'              {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText '--channel 缺少通道值' '--channel requires a channel value') }
                $parsed.Channel = $Tokens[++$i]; continue
            }
            '^(-s|--source)$'            {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText "$t 缺少源名称" "$t requires a source name") }
                $parsed.Source = $Tokens[++$i]; continue
            }
            '^(--scope)$'                {
                if ($i + 1 -ge @($Tokens).Count) { throw (Get-LocalizedText '--scope 缺少范围值' '--scope requires a scope value') }
                $parsed.Scope = $Tokens[++$i]; continue
            }
            '^(--force|-f)$'             { $parsed.Force = $true; continue }
            '^(--disable-interactivity)$' { $parsed.NonInteractive = $true; continue }
            '^(--accept-package-agreements|--accept-source-agreements|--silent|--interactive|-i|--verbose|--verbose-logs|--ignore-warnings|--exact|-e)$' { continue }  # 兼容 winget，忽略
            '^-.*'                       { throw (Get-LocalizedText "未知参数：$t（wingets --help 查看用法）" "Unknown option: $t (run wingets --help for usage)") }
            default                      { $parsed.Positional = @($parsed.Positional) + $t }
        }
    }
    # 动词与目标：第一个位置参数是动词，其余为目标
    $pos = @($parsed.Positional | Where-Object { $_ })
    if ($pos.Count -gt 0 -and $script:UnsupportedVerbs -contains $pos[0].ToLower()) {
        throw (Get-LocalizedText "不支持 winget 动词 '$($pos[0])'：wingets 只处理 Microsoft Store 包的查询、下载、安装和卸载。" "Unsupported winget verb '$($pos[0])': wingets only queries, downloads, installs, and uninstalls Microsoft Store packages.")
    }
    if ($pos.Count -gt 0 -and $script:ValidVerbs -contains $pos[0].ToLower()) {
        $parsed.Verb   = $pos[0].ToLower()
        $parsed.Target = if ($pos.Count -gt 1) { $pos[1] } else { $null }
        if ($pos.Count -gt 2) { throw (Get-LocalizedText "位置参数过多：$($pos[2..($pos.Count - 1)] -join ' ')" "Too many positional arguments: $($pos[2..($pos.Count - 1)] -join ' ')") }
    } else {
        if ($pos.Count -gt 0) {
            # 无动词但有目标：默认 install（兼容 wingets <id> 简写）
            $parsed.Verb = 'install'
            $parsed.Target = $pos[0]
        } elseif (-not $parsed.Help -and -not $parsed.Version) {
            # 完全无参数（也没有 --help/--version 等旗标）：显示帮助
            $parsed.Help = $true
        }
    }
    if (-not $parsed.Target) { $parsed.Target = $parsed.Id }
    if (-not $parsed.Target -and $parsed.Verb -in @('show', 'search')) { $parsed.Target = $parsed.Query }
    if ($parsed.Help) { return $parsed }
    if ($parsed.PackageVersion) {
        throw (Get-LocalizedText "不支持指定包版本 $($parsed.PackageVersion)：Microsoft Store 官方接口只保证返回当前通道的可用版本。" "Package version $($parsed.PackageVersion) is not supported: the Microsoft Store endpoint only guarantees the available version for the current channel.")
    }
    if ($parsed.Source -and $parsed.Source -ne 'msstore') {
        throw (Get-LocalizedText "仅支持 Microsoft Store 源（--source msstore），不支持：$($parsed.Source)" "Only the Microsoft Store source is supported (--source msstore); received: $($parsed.Source)")
    }
    if ($parsed.Scope -and $parsed.Scope -ne 'user') {
        throw (Get-LocalizedText 'Add-AppxPackage 仅按当前用户注册应用，只支持 --scope user。' 'Add-AppxPackage registers apps for the current user; only --scope user is supported.')
    }
    if ($parsed.Arch -notin @('x64', 'x86', 'arm', 'arm64', 'neutral', 'all')) {
        throw (Get-LocalizedText "不支持的架构：$($parsed.Arch)；可用值：x64、x86、arm、arm64、neutral、all。" "Unsupported architecture: $($parsed.Arch); supported values: x64, x86, arm, arm64, neutral, all.")
    }
    if ($parsed.Channel -ne 'Retail') {
        throw (Get-LocalizedText "官方接口模式目前只支持已验证的 Retail 通道，收到：$($parsed.Channel)" "The official-endpoint mode currently supports only the verified Retail channel; received: $($parsed.Channel)")
    }
    return $parsed
}

# ── Microsoft Store / Windows Update 官方接口 ─────────────────
$script:StoreCatalogCache = @{}
$script:StoreServiceUri = 'https://fe3.delivery.mp.microsoft.com/ClientWebService/client.asmx'
$script:StoreSoapHeaders = @{ 'Content-Type' = 'application/soap+xml; charset=utf-8' }

function Get-StoreCatalogData {
    param([Parameter(Mandatory)][string]$ProductId)

    if ($script:StoreCatalogCache.ContainsKey($ProductId)) {
        return $script:StoreCatalogCache[$ProductId]
    }

    $uri = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/products/$ProductId" +
           '?market=US&locale=en-us&deviceFamily=Windows.Desktop'
    $response = Invoke-RestMethod -Uri $uri -TimeoutSec 30
    $sku = @($response.Payload.Skus | Where-Object { $_.FulfillmentData } | Select-Object -First 1)
    if ($sku.Count -eq 0) {
        throw (Get-LocalizedText "产品 $ProductId 没有可用的 Microsoft Store 履行数据。" "Product $ProductId has no usable Microsoft Store fulfillment data.")
    }

    $fulfillment = $sku[0].FulfillmentData | ConvertFrom-Json
    if (-not $fulfillment.WuCategoryId) {
        throw (Get-LocalizedText "产品 $ProductId 没有 WuCategoryId，无法查询 Windows Update 包。" "Product $ProductId has no WuCategoryId, so Windows Update packages cannot be queried.")
    }

    $result = [pscustomobject]@{
        Payload = $response.Payload
        Fulfillment = $fulfillment
    }
    $script:StoreCatalogCache[$ProductId] = $result
    return $result
}

function Convert-Base64Sha1ToHex {
    param([Parameter(Mandatory)][string]$Digest)
    return ([BitConverter]::ToString([Convert]::FromBase64String($Digest))).Replace('-', '')
}

function Get-StoreDeviceAttributes {
    $osVersion = [Environment]::OSVersion.Version.ToString()
    $currentBranch = if ([Environment]::OSVersion.Version.Build -ge 26100) {
        'ge_release'
    } elseif ([Environment]::OSVersion.Version.Build -ge 22000) {
        'ni_release'
    } else {
        'vb_release'
    }
    return "BranchReadinessLevel=CB;CurrentBranch=$currentBranch;FlightRing=Retail;" +
           'InstallLanguage=en-US;OSUILocale=en-US;InstallationType=Client;' +
           'FlightingBranchName=;OSSkuId=48;FlightContent=Branch;App=WU;' +
           "AppVer=$osVersion;OSArchitecture=AMD64;UpdateManagementGroup=2;" +
           "IsFlightingEnabled=0;TelemetryLevel=3;OSVersion=$osVersion;DeviceFamily=Windows.Desktop;"
}

function Invoke-StoreSoapRequest {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$Body,
        [int]$TimeoutSec = 60
    )
    return Invoke-RestMethod -Uri $Uri -Method Post -Headers $script:StoreSoapHeaders -Body $Body -TimeoutSec $TimeoutSec
}

function Get-StoreCookie {
    $request = @"
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://www.w3.org/2005/08/addressing">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/GetCookie</a:Action>
    <a:MessageID>urn:uuid:$([guid]::NewGuid())</a:MessageID>
    <a:To s:mustUnderstand="1">$script:StoreServiceUri</a:To>
    <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization">
        <TicketType Name="MSA" Version="1.0" Policy="MBI_SSL"><user /></TicketType>
      </wuws:WindowsUpdateTicketsToken>
    </o:Security>
  </s:Header>
  <s:Body><GetCookie xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService" /></s:Body>
</s:Envelope>
"@
    $response = Invoke-StoreSoapRequest -Uri $script:StoreServiceUri -Body $request -TimeoutSec 30
    $node = $response.GetElementsByTagName('EncryptedData') | Select-Object -First 1
    if ($null -eq $node -or -not $node.InnerText) {
        throw (Get-LocalizedText 'Microsoft Windows Update 未返回会话 Cookie。' 'Microsoft Windows Update did not return a session cookie.')
    }
    return $node.InnerText
}

function Get-StoreUpdateMetadata {
    param(
        [Parameter(Mandatory)][string]$CategoryId,
        [Parameter(Mandatory)][string]$Cookie,
        [Parameter(Mandatory)][string]$DeviceAttributes
    )

    $created = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $expires = [DateTime]::UtcNow.AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $cookieExpires = [DateTime]::UtcNow.AddYears(10).ToString('yyyy-MM-ddTHH:mm:ssZ')
    $request = @"
<s:Envelope xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/SyncUpdates</a:Action>
    <a:MessageID>urn:uuid:$([guid]::NewGuid())</a:MessageID>
    <a:To s:mustUnderstand="1">$script:StoreServiceUri</a:To>
    <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <Timestamp xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><Created>$created</Created><Expires>$expires</Expires></Timestamp>
      <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization"><TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">Retail</TicketType></wuws:WindowsUpdateTicketsToken>
    </o:Security>
  </s:Header>
  <s:Body>
    <SyncUpdates xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService">
      <cookie><Expiration>$cookieExpires</Expiration><EncryptedData>$Cookie</EncryptedData></cookie>
      <parameters>
        <ExpressQuery>false</ExpressQuery><InstalledNonLeafUpdateIDs><int>1</int><int>2</int><int>11</int><int>23110993</int></InstalledNonLeafUpdateIDs><OtherCachedUpdateIDs />
        <SkipSoftwareSync>false</SkipSoftwareSync><NeedTwoGroupOutOfScopeUpdates>true</NeedTwoGroupOutOfScopeUpdates>
        <FilterAppCategoryIds><CategoryIdentifier><Id>$CategoryId</Id></CategoryIdentifier></FilterAppCategoryIds>
        <TreatAppCategoryIdsAsInstalled>true</TreatAppCategoryIdsAsInstalled><AlsoPerformRegularSync>false</AlsoPerformRegularSync><ComputerSpec />
        <ExtendedUpdateInfoParameters><XmlUpdateFragmentTypes><XmlUpdateFragmentType>Extended</XmlUpdateFragmentType></XmlUpdateFragmentTypes><Locales><string>en-US</string><string>en</string></Locales></ExtendedUpdateInfoParameters>
        <ClientPreferredLanguages><string>en-US</string></ClientPreferredLanguages>
        <ProductsParameters><SyncCurrentVersionOnly>false</SyncCurrentVersionOnly><DeviceAttributes>$DeviceAttributes</DeviceAttributes><CallerAttributes>Interactive=1;IsSeeker=0;</CallerAttributes><Products /></ProductsParameters>
      </parameters>
    </SyncUpdates>
  </s:Body>
</s:Envelope>
"@
    $response = Invoke-StoreSoapRequest -Uri $script:StoreServiceUri -Body $request
    return [xml]$response.InnerXml.Replace('&lt;', '<').Replace('&gt;', '>')
}

function Get-StoreFileLocations {
    param(
        [Parameter(Mandatory)][string]$UpdateId,
        [Parameter(Mandatory)][string]$RevisionNumber,
        [Parameter(Mandatory)][string]$DeviceAttributes
    )

    $securedUri = "$script:StoreServiceUri/secured"
    $created = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $expires = [DateTime]::UtcNow.AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $request = @"
<s:Envelope xmlns:a="http://www.w3.org/2005/08/addressing" xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService/GetExtendedUpdateInfo2</a:Action>
    <a:MessageID>urn:uuid:$([guid]::NewGuid())</a:MessageID><a:To s:mustUnderstand="1">$securedUri</a:To>
    <o:Security s:mustUnderstand="1" xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <Timestamp xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><Created>$created</Created><Expires>$expires</Expires></Timestamp>
      <wuws:WindowsUpdateTicketsToken wsu:id="ClientMSA" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd" xmlns:wuws="http://schemas.microsoft.com/msus/2014/10/WindowsUpdateAuthorization"><TicketType Name="MSA" Version="1.0" Policy="MBI_SSL">Retail</TicketType></wuws:WindowsUpdateTicketsToken>
    </o:Security>
  </s:Header>
  <s:Body><GetExtendedUpdateInfo2 xmlns="http://www.microsoft.com/SoftwareDistribution/Server/ClientWebService"><updateIDs><UpdateIdentity><UpdateID>$UpdateId</UpdateID><RevisionNumber>$RevisionNumber</RevisionNumber></UpdateIdentity></updateIDs><infoTypes><XmlUpdateFragmentType>FileUrl</XmlUpdateFragmentType><XmlUpdateFragmentType>FileDecryption</XmlUpdateFragmentType></infoTypes><deviceAttributes>$DeviceAttributes</deviceAttributes></GetExtendedUpdateInfo2></s:Body>
</s:Envelope>
"@
    $response = Invoke-StoreSoapRequest -Uri $securedUri -Body $request
    $locations = @{}
    foreach ($node in @($response.GetElementsByTagName('FileLocation'))) {
        $digestNode = $node.GetElementsByTagName('FileDigest') | Select-Object -First 1
        $urlNode = $node.GetElementsByTagName('Url') | Select-Object -First 1
        if ($null -eq $digestNode -or $null -eq $urlNode -or -not $urlNode.InnerText) { continue }

        $uri = [uri]$urlNode.InnerText
        if ($uri.Host -notlike '*.delivery.mp.microsoft.com') {
            throw (Get-LocalizedText "Windows Update 返回了非 Microsoft CDN 链接：$($uri.Host)" "Windows Update returned a non-Microsoft CDN URL: $($uri.Host)")
        }
        if ($uri.Scheme -notin @('http', 'https')) {
            throw (Get-LocalizedText "Windows Update 返回了不支持的 URL 协议：$($uri.Scheme)" "Windows Update returned an unsupported URL scheme: $($uri.Scheme)")
        }
        # 部分 tlu CDN 节点仅为返回的 HTTP 主机名配置了正确路由；强改 HTTPS
        # 会触发证书名不匹配。完整性由 HTTPS SOAP 元数据中的 SHA-1 与包签名保证。
        $locations[$digestNode.InnerText] = $uri.AbsoluteUri
    }
    return $locations
}

# ── 查询产品离线包 ────────────────────────────────────────────
function Get-StorePackages {
    param([string]$ProductId, [string]$Channel)

    if ($Channel -ne 'Retail') {
        throw (Get-LocalizedText "官方接口模式目前只支持已验证的 Retail 通道，收到：$Channel" "The official-endpoint mode currently supports only the verified Retail channel; received: $Channel")
    }
    Write-Host (Get-LocalizedText "┣━ 正在从 Microsoft Store 检索包信息 [$ProductId]（通道：Retail）..." "┣━ Querying Microsoft Store packages [$ProductId] (channel: Retail)...") -ForegroundColor Cyan

    $catalog = Get-StoreCatalogData -ProductId $ProductId
    $cookie = Get-StoreCookie
    $deviceAttributes = Get-StoreDeviceAttributes
    $metadata = Get-StoreUpdateMetadata -CategoryId $catalog.Fulfillment.WuCategoryId -Cookie $cookie -DeviceAttributes $deviceAttributes

    $updates = @{}
    foreach ($node in @($metadata.GetElementsByTagName('SecuredFragment'))) {
        $updateInfo = $node.ParentNode.ParentNode.ParentNode
        $numericId = ($updateInfo.GetElementsByTagName('ID') | Select-Object -First 1).InnerText
        $identity = $node.ParentNode.ParentNode.GetElementsByTagName('UpdateIdentity') | Select-Object -First 1
        if ($numericId -and $null -ne $identity) {
            $updates[$numericId] = [pscustomobject]@{
                UpdateId = $identity.UpdateID
                RevisionNumber = $identity.RevisionNumber
            }
        }
    }

    $files = foreach ($node in @($metadata.GetElementsByTagName('File'))) {
        $installerId = $node.GetAttribute('InstallerSpecificIdentifier')
        $fileName = $node.GetAttribute('FileName')
        $extension = [IO.Path]::GetExtension($fileName)
        if (-not $installerId -or $extension -notmatch '^\.(appx|msix|appxbundle|msixbundle)$') { continue }

        $updateInfo = $node.ParentNode.ParentNode.ParentNode
        $numericId = ($updateInfo.GetElementsByTagName('ID') | Select-Object -First 1).InnerText
        if (-not $updates.ContainsKey($numericId)) { continue }

        $digest = $node.GetAttribute('Digest')
        [pscustomobject]@{
            NumericId = $numericId
            Name = "${installerId}_${fileName}"
            Digest = $digest
            SHA1 = Convert-Base64Sha1ToHex -Digest $digest
            SizeBytes = [long]$node.GetAttribute('Size')
        }
    }

    $links = foreach ($group in @($files | Group-Object NumericId)) {
        $update = $updates[$group.Name]
        $locations = Get-StoreFileLocations -UpdateId $update.UpdateId -RevisionNumber $update.RevisionNumber -DeviceAttributes $deviceAttributes
        foreach ($file in $group.Group) {
            if (-not $locations.ContainsKey($file.Digest)) { continue }
            [pscustomobject]@{
                Name = $file.Name
                URL = $locations[$file.Digest]
                SHA1 = $file.SHA1
                Size = Format-ByteSize -Bytes $file.SizeBytes
                Channel = 'Retail'
            }
        }
    }

    $links = @($links | Sort-Object Name -Unique)
    if ($links.Count -eq 0) {
        throw (Get-LocalizedText '未查询到可安装包。请在 apps.microsoft.com 应用详情页 URL 中确认产品 ID。' 'No installable package was found. Verify the product ID in the apps.microsoft.com product URL.')
    }
    return $links
}

# ── 架构过滤 + 版本去重：只留每个包的最新版本 ────────────────
function Select-TargetPackages {
    param($Links, [string]$Arch)
    # 商店 CDN 会列出全部历史版本，逐版本对比后只保留最新；
    # .eappx/.eappxbundle 为加密包（无许可证无法安装），直接排除
    $filtered = @($Links | Where-Object {
        $_.Name -notlike '*.BlockMap' -and
        $_.Name -notmatch '_split\.language-' -and
        $_.Name -notmatch '\.eappx' -and
        ($Arch -eq 'all' -or $_.Name -match "_${Arch}" -or $_.Name -match '_neutral')
    })
    if ($filtered.Count -eq 0) {
        throw (Get-LocalizedText "按架构 $Arch 过滤后没有可下载的包，试试 -a all 查看全部。" "No downloadable package remains after filtering for $Arch; use -a all to include every architecture.")
    }
    $latest = @(
        $filtered | Group-Object {
            $parts = $_.Name -split '_'
            "$($parts[0])|$(if ($parts.Count -ge 3) { $parts[2] })"   # 按包名+架构分组
        } | ForEach-Object {
            $_.Group | Sort-Object {
                try { [version](($_.Name -split '_')[1]) } catch { [version]'0.0' }
            } -Descending | Select-Object -First 1
        }
    )
    return $latest
}

# ── 下载 + SHA1 校验 ───────────────────────────────────────────
$script:DownloadUA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0'

function Format-ByteSize {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return '{0:N2} GiB' -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return '{0:N1} MiB' -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return '{0:N1} KiB' -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Test-InteractiveOutput {
    try { return -not [Console]::IsOutputRedirected }
    catch { return $true }
}

function Save-UrlWithProgress {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$DisplayName
    )

    Add-Type -AssemblyName System.Net.Http
    $partialPath = "$Destination.download"
    $handler = $null
    $client = $null
    $request = $null
    $response = $null
    $sourceStream = $null
    $destinationStream = $null
    $completed = $false
    $interactive = Test-InteractiveOutput
    $progressId = 1

    Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
    try {
        $handler = [Net.Http.HttpClientHandler]::new()
        $client = [Net.Http.HttpClient]::new($handler)
        $client.Timeout = [TimeSpan]::FromHours(6)
        $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get, $Uri)
        $null = $request.Headers.TryAddWithoutValidation('User-Agent', $script:DownloadUA)
        $response = $client.SendAsync(
            $request,
            [Net.Http.HttpCompletionOption]::ResponseHeadersRead
        ).GetAwaiter().GetResult()
        $null = $response.EnsureSuccessStatusCode()

        $totalBytes = if ($null -ne $response.Content.Headers.ContentLength) {
            [long]$response.Content.Headers.ContentLength
        } else { 0L }
        $sourceStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $destinationStream = [IO.File]::Open(
            $partialPath,
            [IO.FileMode]::Create,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )

        $buffer = New-Object byte[] (1MB)
        $downloadedBytes = 0L
        $stopwatch = [Diagnostics.Stopwatch]::StartNew()
        $lastDisplay = [TimeSpan]::Zero
        $lastConsoleDisplay = [TimeSpan]::Zero
        while (($read = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $destinationStream.Write($buffer, 0, $read)
            $downloadedBytes += $read
            if (($stopwatch.Elapsed - $lastDisplay).TotalMilliseconds -lt 200) { continue }

            $lastDisplay = $stopwatch.Elapsed
            $downloaded = Format-ByteSize -Bytes $downloadedBytes
            $speed = if ($stopwatch.Elapsed.TotalSeconds -gt 0) {
                Format-ByteSize -Bytes ([long]($downloadedBytes / $stopwatch.Elapsed.TotalSeconds))
            } else { '0 B' }
            if ($totalBytes -gt 0) {
                $percent = [Math]::Min(100, [int](100 * $downloadedBytes / $totalBytes))
                $status = "$downloaded / $(Format-ByteSize -Bytes $totalBytes)  $percent%  $speed/s"
            } else {
                $percent = -1
                $status = "$downloaded  $speed/s"
            }

            if ($interactive) {
                Write-Progress -Id $progressId -Activity (Get-LocalizedText "下载 $DisplayName" "Downloading $DisplayName") -Status $status -PercentComplete $percent
            } elseif (($stopwatch.Elapsed - $lastConsoleDisplay).TotalSeconds -ge 5) {
                Write-Host (Get-LocalizedText "┃      进度：$status" "┃      Progress: $status")
                $lastConsoleDisplay = $stopwatch.Elapsed
            }
        }

        $destinationStream.Flush()
        $destinationStream.Dispose()
        $destinationStream = $null
        Move-Item -LiteralPath $partialPath -Destination $Destination -Force
        $completed = $true
        Write-Host (Get-LocalizedText "┃      完成：$(Format-ByteSize -Bytes $downloadedBytes)" "┃      Complete: $(Format-ByteSize -Bytes $downloadedBytes)") -ForegroundColor Green
    } finally {
        if ($interactive) {
            Write-Progress -Id $progressId -Activity (Get-LocalizedText "下载 $DisplayName" "Downloading $DisplayName") -Completed
        }
        if ($null -ne $destinationStream) { $destinationStream.Dispose() }
        if ($null -ne $sourceStream) { $sourceStream.Dispose() }
        if ($null -ne $response) { $response.Dispose() }
        if ($null -ne $request) { $request.Dispose() }
        if ($null -ne $client) { $client.Dispose() }
        if ($null -ne $handler) { $handler.Dispose() }
        if (-not $completed) {
            Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Save-Package {
    param($Targets, [string]$OutDir)
    foreach ($t in $Targets) {
        $dest = Join-Path $OutDir $t.Name
        if ((Test-Path $dest) -and $t.SHA1 -and ((Get-FileHash $dest -Algorithm SHA1).Hash -eq $t.SHA1)) {
            Write-Host (Get-LocalizedText "┃    已存在（SHA1 校验通过，跳过）：$($t.Name)" "┃    Already present (SHA1 verified, skipped): $($t.Name)") -ForegroundColor DarkGray
            continue
        }
        Write-Host (Get-LocalizedText "┃    下载：$($t.Name) ($($t.Size))" "┃    Downloading: $($t.Name) ($($t.Size))") -ForegroundColor Cyan
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Save-UrlWithProgress -Uri $t.URL -Destination $dest -DisplayName $t.Name
                if ($t.SHA1) {
                    $actual = (Get-FileHash $dest -Algorithm SHA1).Hash
                    if ($actual -ne $t.SHA1) {
                        Remove-Item $dest -Force -ErrorAction SilentlyContinue
                        throw (Get-LocalizedText "SHA1 校验失败：$($t.Name)" "SHA1 verification failed: $($t.Name)")
                    }
                }
                break
            } catch {
                if ($attempt -eq 3) { throw }
                Write-Host (Get-LocalizedText "┃      第 $attempt 次下载失败，3 秒后重试：$($_.Exception.Message)" "┃      Download attempt $attempt failed; retrying in 3 seconds: $($_.Exception.Message)") -ForegroundColor Yellow
                Start-Sleep -Seconds 3
            }
        }
    }
}

# ── Add-AppxPackage 异步执行 + 安装状态 ────────────────────────
function Install-AppxPackageWithProgress {
    param(
        [Parameter(Mandatory)][string]$Path,
        [string[]]$DependencyPath = @()
    )

    $interactive = Test-InteractiveOutput
    $progressId = 2
    $packageName = Split-Path $Path -Leaf
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $lastConsoleDisplay = [TimeSpan]::Zero
    $spinner = @('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')
    $spinnerIndex = 0
    $installer = [PowerShell]::Create()
    $asyncResult = $null

    try {
        $null = $installer.AddScript({
            param($PackagePath, $Dependencies)
            $ErrorActionPreference = 'Stop'
            if (@($Dependencies).Count -gt 0) {
                Add-AppxPackage -Path $PackagePath -DependencyPath @($Dependencies) -ErrorAction Stop
            } else {
                Add-AppxPackage -Path $PackagePath -ErrorAction Stop
            }
        }).AddArgument($Path).AddArgument(@($DependencyPath))
        $asyncResult = $installer.BeginInvoke()

        while (-not $asyncResult.AsyncWaitHandle.WaitOne(250)) {
            $elapsed = [int]$stopwatch.Elapsed.TotalSeconds
            $status = Get-LocalizedText "$($spinner[$spinnerIndex % $spinner.Count]) 正在注册 $packageName（已用时 ${elapsed}s）" "$($spinner[$spinnerIndex % $spinner.Count]) Registering $packageName (${elapsed}s elapsed)"
            $spinnerIndex++
            if ($interactive) {
                Write-Progress -Id $progressId -Activity (Get-LocalizedText '安装 Microsoft Store 应用包' 'Installing Microsoft Store package') -Status $status -PercentComplete -1
            } elseif (($stopwatch.Elapsed - $lastConsoleDisplay).TotalSeconds -ge 5) {
                Write-Host "┃    $status"
                $lastConsoleDisplay = $stopwatch.Elapsed
            }
        }

        $null = $installer.EndInvoke($asyncResult)
        if ($installer.Streams.Error.Count -gt 0) {
            throw ($installer.Streams.Error | ForEach-Object { $_.ToString() } | Out-String).Trim()
        }
    } finally {
        if ($interactive) {
            Write-Progress -Id $progressId -Activity (Get-LocalizedText '安装 Microsoft Store 应用包' 'Installing Microsoft Store package') -Completed
        }
        if ($null -ne $asyncResult -and -not $asyncResult.IsCompleted) {
            $installer.Stop()
        }
        $installer.Dispose()
    }
}

# ── 显示包列表（show/search）─────────────────────────────────
function Show-PackageList {
    param($Links)
    if ($script:IsChinese) {
        $rows = foreach ($l in $Links) {
            [pscustomobject]@{
                名称 = $l.Name
                大小 = $l.Size
                SHA1 = $l.SHA1
                通道 = $l.Channel
            }
        }
    } else {
        $rows = foreach ($l in $Links) {
            [pscustomobject]@{
                Name = $l.Name
                Size = $l.Size
                SHA1 = $l.SHA1
                Channel = $l.Channel
            }
        }
    }
    $rows | Format-Table -AutoSize | Out-String -Width 170 | ForEach-Object { Write-Host $_ }
}

# ── 通过商店 edge API 取 PackageFamilyName ───────────────────
function Get-FamilyName {
    param([string]$ProductId)
    try {
        return (Get-StoreCatalogData -ProductId $ProductId).Fulfillment.PackageFamilyName
    } catch {
        Write-Host (Get-LocalizedText '┗━ 未获取到 PackageFamilyName，将按体积推断主包。' '┗━ PackageFamilyName was unavailable; the largest package will be treated as the main package.') -ForegroundColor DarkYellow
        return $null
    }
}

# ── 主流程：install / download ────────────────────────────────
function Invoke-InstallOrDownload {
    param($Opts, [switch]$Install)

    if (-not $Opts.Target) { throw (Get-LocalizedText '缺少产品 ID。用法：wingets install <productId> --help 查看详情' 'Missing product ID. Usage: wingets install <productId>; run wingets --help for details.') }
    $family = Get-FamilyName -ProductId $Opts.Target
    $appName = if ($family) { $family -replace '_[^_]+$', '' } else { $null }

    # 安装前先检查已装状态（避免无谓的大流量下载）
    if ($Install -and -not $Opts.Force -and $appName) {
        $installed = Get-AppxPackage -Name $appName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($installed) {
            Write-Host (Get-LocalizedText "┣━ 已安装：$($installed.PackageFullName)（版本 $($installed.Version)，状态 $($installed.Status)）" "┣━ Already installed: $($installed.PackageFullName) (version $($installed.Version), status $($installed.Status))") -ForegroundColor Yellow
            Write-Host (Get-LocalizedText '┗━ 如需覆盖重装（例如修复损坏包），请追加 --force 参数。' '┗━ Add --force to reinstall, for example to repair a damaged package.') -ForegroundColor Yellow
            return
        }
    }

    $links = Get-StorePackages -ProductId $Opts.Target -Channel $Opts.Channel
    if ($Opts.Verb -eq 'show' -or $Opts.Verb -eq 'search') { Show-PackageList -Links $links; return }

    $targets = Select-TargetPackages -Links $links -Arch $Opts.Arch
    Write-Host (Get-LocalizedText '┣━ 将下载以下包：' '┣━ Packages to download:') -ForegroundColor Cyan
    foreach ($p in $targets) {
        Write-Host "┃    $($p.Name)  ($($p.Size))"
    }

    if (-not (Test-Path $Opts.Out)) { New-Item -Path $Opts.Out -ItemType Directory -Force | Out-Null }
    Write-Host (Get-LocalizedText "┣━ 开始下载到 $($Opts.Out) ..." "┣━ Downloading to $($Opts.Out) ...") -ForegroundColor Cyan
    Save-Package -Targets $targets -OutDir $Opts.Out
    Write-Host (Get-LocalizedText '┣━ 下载完成（已通过 SHA1 校验）。' '┣━ Download complete (SHA1 verified).') -ForegroundColor Green

    if (-not $Install) { return }

    # 识别主包与依赖包
    $files = @($targets | ForEach-Object { Join-Path $Opts.Out $_.Name } | Where-Object { Test-Path $_ })
    $main = $null
    if ($appName) {
        $main = $files | Where-Object { ([IO.Path]::GetFileName($_) -like "$appName*") } |
            Sort-Object { (Get-Item $_).Length } -Descending | Select-Object -First 1
    }
    if (-not $main) {
        $main = $files | Sort-Object { (Get-Item $_).Length } -Descending | Select-Object -First 1
    }
    $deps = @($files | Where-Object { $_ -ne $main })
    Write-Host (Get-LocalizedText "┣━ 主包：$(Split-Path $main -Leaf)" "┣━ Main package: $(Split-Path $main -Leaf)") -ForegroundColor Cyan
    if ($deps.Count) {
        $depNames = ($deps | ForEach-Object { Split-Path $_ -Leaf }) -join ', '
        Write-Host (Get-LocalizedText "┃    依赖：$depNames" "┃    Dependencies: $depNames")
    }

    # --force：先卸载旧包。Remove-AppxPackage 可能同时清除该用户的应用数据。
    if ($appName) {
        $installed = Get-AppxPackage -Name $appName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($installed -and $Opts.Force) {
            Write-Host (Get-LocalizedText "┣━ --force：卸载旧包 $($installed.PackageFullName) ..." "┣━ --force: uninstalling existing package $($installed.PackageFullName) ...") -ForegroundColor Yellow
            $installed | Remove-AppxPackage
        }
    }

    Write-Host (Get-LocalizedText '┣━ 正在 Add-AppxPackage 安装...' '┣━ Installing with Add-AppxPackage...') -ForegroundColor Cyan
    try {
        # 优先单装主包：系统会自动解析已安装的框架依赖（与商店行为一致）
        Install-AppxPackageWithProgress -Path $main
    } catch {
        # 回退：把下载的依赖包一并传入
        Write-Host (Get-LocalizedText '┃    系统依赖解析失败，改用下载的依赖包重装...' '┃    System dependency resolution failed; retrying with the downloaded dependencies...') -ForegroundColor Yellow
        if ($deps.Count) {
            Install-AppxPackageWithProgress -Path $main -DependencyPath $deps
        } else {
            throw
        }
    }

    if ($appName) {
        $pkg = Get-AppxPackage -Name $appName -ErrorAction SilentlyContinue | Select-Object -First 1
        Write-Host (Get-LocalizedText "┗━ 已成功安装：$($pkg.PackageFullName)（状态：$($pkg.Status)）" "┗━ Installed successfully: $($pkg.PackageFullName) (status: $($pkg.Status))") -ForegroundColor Green
    } else {
        Write-Host (Get-LocalizedText '┗━ 已成功安装。' '┗━ Installed successfully.') -ForegroundColor Green
    }
}

# ── 主流程：uninstall ─────────────────────────────────────────
function Invoke-Uninstall {
    param($Opts)
    if (-not $Opts.Target -and -not $Opts.Name) { throw (Get-LocalizedText '缺少包名。用法：wingets uninstall <包名> [-n 名称] [--force]' 'Missing package name. Usage: wingets uninstall <name> [-n name] [--force]') }
    if ($Opts.NonInteractive -and -not $Opts.Force) {
        throw (Get-LocalizedText 'uninstall 使用 --disable-interactivity 时必须同时指定 --force，以免等待确认输入。' 'uninstall requires --force with --disable-interactivity to avoid waiting for confirmation input.')
    }
    $name = if ($Opts.Name) { $Opts.Name } else { $Opts.Target }
    $pkgs = @(Get-AppxPackage -Name $name -ErrorAction SilentlyContinue)
    if ($pkgs.Count -eq 0) { throw (Get-LocalizedText "未找到已安装包：$name" "Installed package not found: $name") }
    foreach ($p in $pkgs) {
        Write-Host (Get-LocalizedText "┣━ 将卸载：$($p.PackageFullName)" "┣━ Package to uninstall: $($p.PackageFullName)") -ForegroundColor Yellow
        if (-not $Opts.Force) {
            $answer = Read-Host (Get-LocalizedText '┃    确认卸载？(y/N)' '┃    Confirm uninstall? (y/N)')
            if ($answer -notmatch '^(?i:y|yes)$') { Write-Host (Get-LocalizedText '┗━ 已取消。' '┗━ Cancelled.'); continue }
        }
        $p | Remove-AppxPackage
        Write-Host (Get-LocalizedText '┗━ 已卸载。应用数据是否保留取决于包自身与 Windows 的卸载行为。' '┗━ Uninstalled. App data retention depends on the package and Windows uninstall behavior.') -ForegroundColor Green
    }
}

# ── 入口分发 ──────────────────────────────────────────────────
try {
    $opts = Parse-Arguments
    if ($opts.Help)     { Show-Help; return }
    if ($opts.Version)  { Write-Host 'wingets v1.2 (Microsoft Store + Windows Update + Add-AppxPackage)'; return }

    switch ($opts.Verb) {
        'install'   { Invoke-InstallOrDownload -Opts $opts -Install }
        'download'  { Invoke-InstallOrDownload -Opts $opts }
        { $_ -in 'show', 'search' } {
            if (-not $opts.Target) { throw (Get-LocalizedText '缺少产品 ID。用法：wingets show <productId>' 'Missing product ID. Usage: wingets show <productId>') }
            $links = Get-StorePackages -ProductId $opts.Target -Channel $opts.Channel
            Show-PackageList -Links $links
        }
        'uninstall' { Invoke-Uninstall -Opts $opts }
        default     { Show-Help }
    }
} catch {
    Write-Host (Get-LocalizedText "┗━ 错误：$($_.Exception.Message)" "┗━ Error: $($_.Exception.Message)") -ForegroundColor Red
    exit 1
}
