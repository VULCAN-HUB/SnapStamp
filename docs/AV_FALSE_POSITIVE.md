# 백신 오탐(False Positive) 대응 — SnapStamp 배포 절차

행사 당일 백신이 실행을 막으면 그날 부스가 통째로 죽는다. 배포 전에 이 문서의 절차를 그대로 밟는다.
자본이 드는 항목(EV 코드사이닝 인증서)은 v3 이후로 보류이며, 여기 있는 것은 **전부 무료**다.

## 1. 왜 오탐이 나는가

PyInstaller `onefile` 실행 파일은 실행할 때마다 **128MB를 임시폴더에 스스로 풀고 그것을 실행**한다.
이 동작 패턴(자가추출 후 실행)이 패커형 악성코드와 구분이 안 돼 휴리스틱을 때린다.
여기에 **디지털 서명이 없으면** SmartScreen 평판 점수도 0에서 시작한다.

## 2. 적용한 대응 (빌드 측)

| 대응 | 상태 | 근거 |
|---|---|---|
| **배포 기본형을 onedir(폴더)로 전환** | 적용 | 자가추출이 없어져 대표 트리거 제거. 기동도 3.95s→1.36s로 **2.9배 빠름**(실측) |
| UPX 압축 사용 안 함 | 적용 | UPX 패킹은 오탐 1순위 원인. `build.spec`에서 `upx=False` 명시 |
| 버전 메타데이터 완비 | 적용 | CompanyName/ProductName/Version 등. 메타 없는 exe는 의심도가 올라간다 |
| SHA-256 체크섬 동봉 | 적용 | 배포 시 `.sha256` 파일 동봉. 사용자 무결성 확인 + 오탐 신고 시 근거 |
| 배포 전 Defender 스캔 | 적용 | `build_win.ps1`이 빌드 끝에 자동 실행 |

`onefile`은 편의용 보조 산출물로만 남긴다(`build_win.ps1 -OneFile`).

## 3. 빌드 명령

```
build_win.bat            # 기본: onedir → SnapStamp.zip (배포용)
build_win.bat -OneFile   # 단일 exe만 (보조)
build_win.bat -Both      # 둘 다
```
산출물은 `dist_out\`(또는 `-OutDir` / 환경변수 `SNAPSTAMP_OUT` 로 지정한 폴더)에 `.sha256`과 함께 놓인다.

## 4. 배포 전 체크리스트

- [ ] `build_win.bat` 실행 → 끝에 Defender "found no threats" 확인
- [ ] `.sha256` 파일이 산출물과 같이 생성됐는지 확인
- [ ] 릴리스에 **onedir ZIP을 기본**으로, onefile exe는 "빠른 실행용(백신 경고 가능)"으로 표기
- [ ] README에 SmartScreen 경고 통과 방법 안내(§6) 포함
- [ ] 새 버전마다 해시가 바뀌므로 릴리스 노트에 해시 갱신

## 5. 오탐이 실제로 발생했을 때 — 무료 신고 창구

신고에는 **파일 + 해시 + "자체 제작 오픈소스 앱이며 오탐"** 사유를 적는다. 보통 1~3일 내 정의 업데이트.

| 백신 | 신고 URL |
|---|---|
| Microsoft Defender | https://www.microsoft.com/en-us/wdsi/filesubmission |
| AhnLab (V3/알약 아님) | https://www.ahnlab.com/kr/site/support/tech/reportFile.do |
| ESTsecurity (알약) | https://www.estsecurity.com/support/report |
| 다중 엔진 확인 | VirusTotal (업로드 = 파일 공개이므로 오너 판단 후) |

> ⚠️ VirusTotal 업로드는 바이너리를 외부에 공개 배포하는 행위다. 이미 GitHub에 공개할
> 릴리스 산출물이라면 문제없지만, 미공개 빌드는 올리기 전에 오너 확인을 받는다.

## 6. SmartScreen — 서명 없이 할 수 있는 것

서명이 없으면 최초 실행 시 "Windows에서 PC를 보호했습니다" 화면이 뜬다. **차단이 아니라 경고**이며,
`추가 정보` → `실행`으로 통과된다. README와 다운로드 페이지에 이 안내를 반드시 넣는다.

평판을 쌓는 무료 수단:
- 항상 **같은 GitHub 릴리스 URL**로 배포한다(다운로드 수가 쌓이면 평판이 올라간다).
- 버전마다 파일명을 무작위로 바꾸지 않는다.
- 해시를 공개해 사용자가 대조할 수 있게 한다.

**근본 해결은 EV 코드사이닝 인증서(연 30~50만원대)이며, 자본 항목이라 v3 이후로 보류**한다.
불특정 다수 상대 상용 배포로 넘어가는 시점이 구매 시점이다.

## 7. 알려진 한계

- 이 문서의 대응은 **오탐 확률을 낮출 뿐 0으로 만들지 못한다.** 서명 없는 배포의 구조적 한계다.
- 행사 투입 전에는 **운영 PC에서 미리 한 번 실행해 두는 것**이 가장 확실하다(당일 첫 실행 금지).
