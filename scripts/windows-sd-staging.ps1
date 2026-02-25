[CmdletBinding()]
param(
    [string]$ProjectRoot = ".",
    [string]$OutputDir = "sd_staging",
    [string]$OpenAIApiKey,
    [string]$StopKeyword = "orb sleep",
    [switch]$EnableWakeWord,
    [string]$WakeWord = "orb"
)

$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param([string]$PathValue)
    return (Resolve-Path -Path $PathValue).Path
}

function Ensure-File {
    param([string]$PathValue)
    if (-not (Test-Path -Path $PathValue -PathType Leaf)) {
        throw "Required file not found: $PathValue"
    }
}

function Set-TopLevelScalar {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )

    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^$Key:\s*") {
            $Lines[$i] = "$Key: \"$Value\""
            return
        }
    }

    throw "Could not find top-level key '$Key' in config file."
}

function Set-SectionScalar {
    param(
        [string[]]$Lines,
        [string]$Section,
        [string]$Key,
        [string]$Value,
        [switch]$AsBoolean
    )

    $inSection = $false

    for ($i = 0; $i -lt $Lines.Count; $i++) {
        $line = $Lines[$i]

        if ($line -match '^([a-zA-Z_][a-zA-Z0-9_]*):\s*$') {
            $inSection = ($Matches[1] -eq $Section)
            continue
        }

        if (-not $inSection) {
            continue
        }

        if ($line -match "^\s+$Key:\s*") {
            if ($AsBoolean) {
                $Lines[$i] = "  $Key: $Value"
            }
            else {
                $Lines[$i] = "  $Key: \"$Value\""
            }
            return
        }
    }

    throw "Could not find key '$Section.$Key' in config file."
}

$projectRootResolved = Resolve-AbsolutePath -PathValue $ProjectRoot
$configSource = Join-Path $projectRootResolved "config.yaml"
Ensure-File -PathValue $configSource

$assetFiles = @(
    "ambient_loop.ogg",
    "glass_chime.wav",
    "down_chime.wav"
)

foreach ($asset in $assetFiles) {
    Ensure-File -PathValue (Join-Path $projectRootResolved (Join-Path "assets" $asset))
}

$outputRoot = Join-Path $projectRootResolved $OutputDir
$orbOutDir = Join-Path $outputRoot "orb"
$assetsOutDir = Join-Path $orbOutDir "assets"

New-Item -ItemType Directory -Path $assetsOutDir -Force | Out-Null

$configOutPath = Join-Path $orbOutDir "config.yaml"
Copy-Item -Path $configSource -Destination $configOutPath -Force

$configLines = Get-Content -Path $configOutPath
Set-TopLevelScalar -Lines $configLines -Key "stop_keyword" -Value $StopKeyword
Set-SectionScalar -Lines $configLines -Section "wake_word" -Key "enabled" -Value ($EnableWakeWord.IsPresent.ToString().ToLower()) -AsBoolean
Set-SectionScalar -Lines $configLines -Section "wake_word" -Key "keyword" -Value $WakeWord
Set-Content -Path $configOutPath -Value $configLines -Encoding UTF8

foreach ($asset in $assetFiles) {
    $source = Join-Path $projectRootResolved (Join-Path "assets" $asset)
    Copy-Item -Path $source -Destination (Join-Path $assetsOutDir $asset) -Force
}

if (-not $OpenAIApiKey) {
    $OpenAIApiKey = Read-Host "Enter your OpenAI API key"
}

$envFilePath = Join-Path $orbOutDir "orb.env"
"OPENAI_API_KEY=$OpenAIApiKey" | Set-Content -Path $envFilePath -Encoding UTF8

$notesPath = Join-Path $outputRoot "README-WINDOWS-STAGING.txt"
@"
Staging complete.

Created files:
- orb/config.yaml
- orb/orb.env
- orb/assets/*.ogg|*.wav

Suggested copy flow to your Raspberry Pi SD card:
1) Flash Raspberry Pi OS and boot the Pi once.
2) Copy this entire 'orb' folder to the Pi home directory (for example with WinSCP or USB transfer).
3) On the Pi, move into the folder and run the Linux setup from README.md.
4) Load API key into shell profile:
   cat orb.env >> ~/.bashrc
   source ~/.bashrc

If you staged to removable media directly, keep the folder path as:
  /home/pi/orb
"@ | Set-Content -Path $notesPath -Encoding UTF8

Write-Host "Staging bundle created at: $outputRoot"
