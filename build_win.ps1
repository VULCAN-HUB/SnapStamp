# SnapStamp Windows 빌드 → _빌드파일 배치
#
# 기본 산출물 = onedir(폴더) 배포용 ZIP. 백신 오탐의 대표 트리거인 '실행 시 자가추출'이
# 없고 기동도 빠르다. 단일 exe가 필요하면  -OneFile  스위치를 준다(편의용 보조 산출물).
#   -OutDir  산출물을 복사할 폴더(기본: 이 프로젝트의 dist_out). 환경에 맞게 지정한다.
param([switch]$OneFile, [switch]$Both, [string]$OutDir)

# ⚠️ 'Stop'으로 두면 안 된다. PyInstaller는 정상 진행 로그를 stderr로 내보내는데,
#    PowerShell 5.1은 네이티브 stderr를 ErrorRecord로 감싸 성공 빌드를 실패로 만든다.
#    성공/실패는 반드시 $LASTEXITCODE로 판정한다.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
# 산출물 폴더: -OutDir > 환경변수 SNAPSTAMP_OUT > 프로젝트 안 dist_out
# (특정 PC의 폴더 구조를 소스에 박지 않는다)
$out = if ($OutDir) { $OutDir }
       elseif ($env:SNAPSTAMP_OUT) { $env:SNAPSTAMP_OUT }
       else { Join-Path $root 'dist_out' }
if (-not (Test-Path $out)) { New-Item -ItemType Directory -Force $out | Out-Null }

function Invoke-Step($label, [scriptblock]$cmd) {
    & $cmd | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "$label 실패 (exit $LASTEXITCODE)" }
}

Invoke-Step '버전 메타 생성' { python make_version_info.py }
Invoke-Step '아이콘 생성'    { python build_icon.py }

function Show-Hash($path) {
    $h = (Get-FileHash $path -Algorithm SHA256).Hash
    $mb = [math]::Round((Get-Item $path).Length / 1MB, 1)
    "  {0}  ({1}MB)`n  SHA256: {2}" -f (Split-Path $path -Leaf), $mb, $h
    # 배포 시 함께 올릴 체크섬 파일(사용자가 무결성 확인 → 오탐 문의 시 근거)
    "$h  $(Split-Path $path -Leaf)" | Out-File "$path.sha256" -Encoding ascii
}

# ── onedir(기본) ─────────────────────────────────────────────────────────
if (-not $OneFile -or $Both) {
    Remove-Item env:SNAPSTAMP_ONEFILE -ErrorAction SilentlyContinue
    Invoke-Step 'onedir 빌드' { pyinstaller --noconfirm build.spec }
    if (-not (Test-Path 'dist\SnapStamp\SnapStamp.exe')) { throw '빌드 실패: dist\SnapStamp\SnapStamp.exe 없음' }
    $zip = Join-Path $out 'SnapStamp.zip'
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path 'dist\SnapStamp' -DestinationPath $zip
    "빌드 완료(onedir):"
    Show-Hash $zip
}

# ── onefile(보조) ────────────────────────────────────────────────────────
if ($OneFile -or $Both) {
    $env:SNAPSTAMP_ONEFILE = '1'
    Invoke-Step 'onefile 빌드' { pyinstaller --noconfirm --distpath dist_onefile --workpath build_onefile build.spec }
    Remove-Item env:SNAPSTAMP_ONEFILE
    if (-not (Test-Path 'dist_onefile\SnapStamp.exe')) { throw '빌드 실패: dist_onefile\SnapStamp.exe 없음' }
    Copy-Item 'dist_onefile\SnapStamp.exe' (Join-Path $out 'SnapStamp.exe') -Force
    "빌드 완료(onefile):"
    Show-Hash (Join-Path $out 'SnapStamp.exe')
}

# ── 배포 전 자체 백신 점검 ───────────────────────────────────────────────
$mp = (Get-ChildItem "$env:ProgramData\Microsoft\Windows Defender\Platform" -Directory |
       Sort-Object Name -Descending | Select-Object -First 1).FullName + '\MpCmdRun.exe'
if (Test-Path $mp) {
    "`nDefender 점검:"
    & $mp -Scan -ScanType 3 -File $out -DisableRemediation
}
