# Real speech is supplied and reviewed by the human; no DAW/AI proposal here.
$ErrorActionPreference = 'Stop'
$voiceBase = Join-Path $env:LOCALAPPDATA 'TKN-DAW-V2'
if (-not (Test-Path -LiteralPath (Join-Path $voiceBase 'voice-env\Scripts\python.exe'))) {
    $voiceBase = Join-Path $env:USERPROFILE 'AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\TKN-DAW-V2'
}
$voicePython = Join-Path $voiceBase 'voice-env\Scripts\python.exe'
$voiceModel = Join-Path $voiceBase 'models\faster-whisper-small'
if (-not (Test-Path -LiteralPath $voicePython) -or -not (Test-Path -LiteralPath $voiceModel)) {
    throw 'Voice environment/model not found. Check README_VOICE.md.'
}
$voiceCases = @(
    @{id='en-track'; phrase='หรี่แทร็ก Voice ลงสองดีบี'; action='REVIEW'},
    @{id='th-track'; phrase='ลดแทร็กเสียงร้องลงสามดีบี'; action='REVIEW'},
    @{id='multiword'; phrase='เพิ่มแทร็ก Lead Vocal ขึ้นหนึ่งจุดห้าดีบี'; action='REVIEW'},
    @{id='negative'; phrase='ตั้งแทร็ก Voice เป็นลบสามจุดศูนย์ห้าดีบี'; action='REVIEW'},
    @{id='zero'; phrase='ตั้งแทร็ก Voice เป็นศูนย์ดีบี'; action='REVIEW'},
    @{id='digit-name'; phrase='หรี่แทร็ก Voice 2 ลงสองดีบี'; action='REVIEW'},
    @{id='silence'; phrase='[Stay silent]'; action='CANCEL if hallucinated text appears'},
    @{id='cancel'; phrase='ลดแทร็ก Voice ลงสองดีบี'; action='CANCEL'}
)
$voiceRun = Join-Path $voiceBase ('acceptance\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $voiceRun | Out-Null
$voiceCases | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $voiceRun 'frozen-cases.json') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $voiceModel 'installation-revision.txt') -Destination (Join-Path $voiceRun 'model-revision.txt')
& $voicePython -m pip freeze | Set-Content -LiteralPath (Join-Path $voiceRun 'dependencies.txt') -Encoding utf8
Start-Transcript -LiteralPath (Join-Path $voiceRun 'console.txt') -NoClobber | Out-Null
try {
    & $voicePython -B (Join-Path $PSScriptRoot 'voice_control.py') devices
    $voiceDevice = [int](Read-Host 'Enter current Brio 300 input index (previously 1)')
    foreach ($voiceCase in $voiceCases) {
        Write-Host "Case: $($voiceCase.id)"
        Write-Host "Speak exactly: $($voiceCase.phrase)"
        Write-Host "Review action: $($voiceCase.action)"
        & $voicePython -B (Join-Path $PSScriptRoot 'voice_control.py') transcribe --stt-model-dir $voiceModel --device $voiceDevice --seconds 8 --out (Join-Path $voiceRun ($voiceCase.id + '.json')) --log (Join-Path $voiceRun ($voiceCase.id + '-console.txt'))
        $voiceExit = $LASTEXITCODE
        $voiceActual = Read-Host 'Did you speak exactly as written? Enter EXACT or describe what you actually said'
        @{id=$voiceCase.id; exit_code=$voiceExit; spoken_attestation=$voiceActual} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $voiceRun ($voiceCase.id + '-attempt.json')) -Encoding utf8
    }
} finally {
    Stop-Transcript | Out-Null
    Write-Host "Evidence directory: $voiceRun"
}
