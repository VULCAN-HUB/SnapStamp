# -*- coding: utf-8 -*-
"""
SnapStamp 실행 안내서 — 논문 초록 스타일 (BETA Ver-0.1)

LogMapping 안내서(make_manual_beta01.py)와 동일한 레이아웃 체계를 따르되,
브랜드 색만 SnapStamp 코발트(#4C7DFF)로 교체했다. 브랜드=Unknown/@unknown8563.

⚠️ PII 금지: 실명·연락처·주소·IP를 넣지 않는다. 노출 가능한 것은 유튜브 이름/주소뿐.

출력: 프로젝트 루트의 "SnapStamp 실행 안내서 (BETA Ver-0.1).pdf"
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Image as RLImage
)
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 ──
FONT_DIR = r"C:\Windows\Fonts"
for name, fname in [("R", "malgun.ttf"), ("B", "malgunbd.ttf")]:
    p = os.path.join(FONT_DIR, fname)
    if os.path.exists(p):
        try:
            pdfmetrics.registerFont(TTFont(name, p))
        except Exception:
            pass
FR, FB = "R", "B"

# ── 색상 (SnapStamp 코발트) ──
ACC       = colors.HexColor("#4C7DFF")
ACC2      = colors.HexColor("#2F5BD6")
ACC_LIGHT = colors.HexColor("#EEF3FF")
ACC_MID   = colors.HexColor("#B9CCFF")
INK       = colors.HexColor("#111111")
DARK      = colors.HexColor("#2C2C2C")
MID       = colors.HexColor("#606060")
LIGHT     = colors.HexColor("#A0A0A0")
RULE      = colors.HexColor("#D5D9E2")
BG_PAGE   = colors.white
BG_BOX    = colors.HexColor("#F7F9FC")

W, H = A4
ML, MR = 2.8 * cm, 2.8 * cm
MT, MB = 2.4 * cm, 2.4 * cm
TW = W - ML - MR


def sty(name, fn=FR, **k):
    return ParagraphStyle(name, fontName=fn, **k)


S = {
    "abs_lbl":  sty("abs_lbl", FB, fontSize=8, textColor=ACC, alignment=TA_LEFT, leading=12, spaceAfter=6),
    "abstract": sty("abstract", FR, fontSize=9.5, textColor=DARK, alignment=TA_JUSTIFY, leading=17),
    "kw":       sty("kw", FR, fontSize=8.5, textColor=MID, alignment=TA_LEFT, leading=13),
    "body":     sty("body", FR, fontSize=9.5, textColor=DARK, alignment=TA_JUSTIFY, leading=17, spaceAfter=3),
    "enum_t":   sty("enum_t", FB, fontSize=9.5, textColor=INK, leading=15, leftIndent=20, spaceAfter=1),
    "enum_d":   sty("enum_d", FR, fontSize=9.5, textColor=MID, leading=15, leftIndent=32, spaceAfter=5),
    "tbl_h":    sty("tbl_h", FB, fontSize=9, textColor=colors.white, leading=13),
    "tbl_c":    sty("tbl_c", FR, fontSize=9, textColor=DARK, leading=14),
    "toc_ch":   sty("toc_ch", FB, fontSize=10, textColor=INK, leading=15, spaceAfter=1),
    "toc_s":    sty("toc_s", FR, fontSize=9.5, textColor=MID, leading=14, leftIndent=16, spaceAfter=1),
    "footnote": sty("footnote", FR, fontSize=8, textColor=MID, alignment=TA_JUSTIFY, leading=13),
}


def sp(n=6):
    return Spacer(1, n)


def P(t, k="body"):
    return Paragraph(t, S[k])


def section_header(num, title):
    t = Table([[Paragraph(f"<b>{num}</b>", ParagraphStyle("sn", fontName=FB, fontSize=11,
                                                          textColor=ACC_MID, alignment=TA_CENTER, leading=15)),
                Paragraph(title, ParagraphStyle("st", fontName=FB, fontSize=12,
                                                textColor=colors.white, leading=15))]],
              colWidths=[1.1 * cm, TW - 1.1 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACC2), ("BACKGROUND", (1, 0), (1, 0), ACC),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "CENTER"),
                           ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                           ("LEFTPADDING", (1, 0), (1, 0), 14)]))
    return t


def subsection_header(num, title):
    BAR = 0.35 * cm
    t = Table([[Paragraph("", ParagraphStyle("bar", leading=14)),
                Paragraph(f"<font color='#4C7DFF'><b>{num}</b></font>  {title}",
                          ParagraphStyle("sh", fontName=FB, fontSize=10, textColor=DARK, leading=14))]],
              colWidths=[BAR, TW - BAR])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACC), ("BACKGROUND", (1, 0), (1, 0), ACC_LIGHT),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                           ("TOPPADDING", (1, 0), (1, 0), 7), ("BOTTOMPADDING", (1, 0), (1, 0), 7),
                           ("LEFTPADDING", (1, 0), (1, 0), 10),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.5, ACC_MID)]))
    return t


def make_table(headers, rows, col_widths=None):
    data = [[Paragraph(h, S["tbl_h"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(c, S["tbl_c"]) for c in r])
    if col_widths is None:
        col_widths = [TW / len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ACC),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_PAGE, ACC_LIGHT]),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                           ("LINEBELOW", (0, 0), (-1, 0), 1.0, ACC2)]))
    return t


def abstract_box(text):
    BAR = 0.35 * cm
    t = Table([[Paragraph("", ParagraphStyle("ab", leading=14)), Paragraph(text, S["abstract"])]],
              colWidths=[BAR, TW - BAR])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACC), ("BACKGROUND", (1, 0), (1, 0), BG_BOX),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                           ("TOPPADDING", (1, 0), (1, 0), 12), ("BOTTOMPADDING", (1, 0), (1, 0), 12),
                           ("LEFTPADDING", (1, 0), (1, 0), 14), ("RIGHTPADDING", (1, 0), (1, 0), 14)]))
    return t


def note_box(text):
    """주의/함정 박스 — 본문과 구분되는 옅은 경고 톤."""
    BAR = 0.35 * cm
    t = Table([[Paragraph("", ParagraphStyle("nb", leading=14)),
                Paragraph(text, sty("note", FR, fontSize=9, textColor=DARK,
                                    alignment=TA_JUSTIFY, leading=15))]],
              colWidths=[BAR, TW - BAR])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#E5A50A")),
                           ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FEF8E7")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                           ("TOPPADDING", (1, 0), (1, 0), 10), ("BOTTOMPADDING", (1, 0), (1, 0), 10),
                           ("LEFTPADDING", (1, 0), (1, 0), 12), ("RIGHTPADDING", (1, 0), (1, 0), 12)]))
    return t


def enum_step(n, title, desc):
    return KeepTogether([P(f"<font color='#4C7DFF'><b>({n})</b></font>  <b>{title}</b>", "enum_t"),
                         P(desc, "enum_d")])


_FIG_N = [0]


def figure(filename, caption, width_ratio=1.0):
    """실제 프로그램 화면 그림 + 캡션. 파일이 없으면 자리표시자를 그린다(빌드는 계속).

    ⚠️ 그림은 `prepare_shots.py`를 거친 배포용(개인정보 마스킹 완료) 이미지만 쓴다.
    """
    _FIG_N[0] += 1
    n = _FIG_N[0]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots", filename)
    w = TW * width_ratio
    cap_style = sty("cap", FR, fontSize=8.5, textColor=MID, alignment=TA_CENTER, leading=13)
    if os.path.exists(path):
        with PILImage.open(path) as im:
            iw, ih = im.size
        img = RLImage(path, width=w, height=w * ih / iw)
    else:
        img = Table([[Paragraph("(화면 이미지 없음)", cap_style)]], colWidths=[w], rowHeights=[3 * cm])
        img.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    box = Table([[img]], colWidths=[w])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, ACC_MID),
                             ("TOPPADDING", (0, 0), (-1, -1), 0),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return KeepTogether([box, sp(4),
                         Paragraph(f"<b>[그림 {n}]</b>  {caption}", cap_style), sp(10)])


def on_page(canvas, doc):
    canvas.saveState()
    n = canvas.getPageNumber()
    if n == 1:
        canvas.setFillColor(ACC); canvas.rect(0, 0, 0.7 * cm, H, fill=1, stroke=0)
        canvas.setFillColor(ACC2); canvas.rect(0, 0, 0.25 * cm, H, fill=1, stroke=0)
    else:
        canvas.setStrokeColor(ACC); canvas.setLineWidth(1.2)
        canvas.line(ML, H - 1.9 * cm, W - MR, H - 1.9 * cm)
        canvas.setFont(FB, 8); canvas.setFillColor(ACC)
        canvas.drawString(ML, H - 1.55 * cm, "SnapStamp")
        canvas.setFont(FR, 8); canvas.setFillColor(LIGHT)
        canvas.drawRightString(W - MR, H - 1.55 * cm, "실행 안내서  ·  BETA Ver-0.1")
        canvas.setStrokeColor(RULE); canvas.setLineWidth(0.5)
        canvas.line(ML, MB - 0.3 * cm, W - MR, MB - 0.3 * cm)
        canvas.setFont(FR, 8); canvas.setFillColor(LIGHT)
        canvas.drawCentredString(W / 2, MB - 0.75 * cm, str(n))
    canvas.restoreState()


def build():
    story = []

    # ── 표지 ──
    cover = Table([[Paragraph("<font color='#4C7DFF'>Snap</font><font color='#F0F2F6'>Stamp</font>",
                              ParagraphStyle("ctitle", fontName=FB, fontSize=40, textColor=colors.white,
                                             leading=48, spaceAfter=4))]], colWidths=[TW])
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B0E13")),
                               ("TOPPADDING", (0, 0), (-1, -1), 42),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(cover)
    cover2 = Table([[Paragraph("실행 안내서", ParagraphStyle("csub", fontName=FR, fontSize=14,
                                                          textColor=colors.HexColor("#C3C9D6"), leading=20))],
                    [Paragraph("이벤트 포토부스 (인생4컷)  ·  BETA Ver-0.1  ·  Windows 10 / 11",
                               ParagraphStyle("cmeta", fontName=FR, fontSize=9,
                                              textColor=colors.HexColor("#6C7385"), leading=13))]],
                   colWidths=[TW])
    cover2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B0E13")),
                                ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 36),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(cover2)
    story.append(sp(20))

    story.append(KeepTogether([
        P("A B S T R A C T", "abs_lbl"),
        abstract_box(
            "본 문서는 SnapStamp BETA Ver-0.1의 설치·설정 및 행사 운영에 관한 실무 안내서다. "
            "SnapStamp는 Windows 환경에서 동작하는 이벤트 포토부스 프로그램으로, 행사 참가자가 "
            "버튼 한 번으로 네 컷을 촬영하면 프로그램이 이를 한 장의 사진으로 합성하고, "
            "짧은 움짤(GIF 또는 MP4)을 함께 만들어 QR 코드로 즉시 전달한다. "
            "사진은 인터넷 업로드 없이 <b>운영 PC 안에서만</b> 보관·전달되므로 참가자의 초상이 "
            "외부 서버로 나가지 않는다. 별도 설치 절차가 없으며 일반 USB 웹캠으로 동작한다. "
            "본 안내서는 최초 실행부터 브랜딩·레이아웃 설정, 손님 수령 페이지 구성, 행사 당일 운영, "
            "문제 해결에 이르는 전 과정을 기술한다."),
        sp(10),
        P("<b>키워드</b>  이벤트 포토부스,  인생4컷,  QR 전달,  로컬 전달,  움짤,  오프라인 운영", "kw"),
    ]))
    story.append(sp(20))
    story.append(make_table(["항목", "내용"], [
        ["문서 버전", "BETA Ver-0.1  (2026년)"],
        ["적용 환경", "Windows 10 / 11  (64비트)"],
        ["전제 조건", "USB 웹캠 1대  ·  손님 휴대폰이 접속할 Wi-Fi (또는 PC 모바일 핫스팟)"],
        ["관리자 권한", "불필요"],
        ["인터넷", "불필요  —  사진은 외부로 전송되지 않음"],
    ], col_widths=[3.5 * cm, TW - 3.5 * cm]))
    story.append(PageBreak())

    # ── 목차 ──
    story.append(KeepTogether([section_header("", "목  차"), sp(12)]))
    toc = [
        ("1.", "설치 및 최초 실행", ["1.1  시스템 요구사항", "1.2  압축 해제와 폴더 구조",
                                "1.3  최초 실행 절차", "1.4  카메라 연결"]),
        ("2.", "설정 — 사진 만들기", ["2.1  레이아웃 · 사진 배치", "2.2  브랜딩 · 색감",
                                 "2.3  촬영 전 보정", "2.4  테스트 촬영과 미리보기"]),
        ("3.", "설정 — 손님 전달", ["3.1  전달 방식과 QR", "3.2  손님 수령 페이지 꾸미기",
                                "3.3  Wi-Fi 접속 안내", "3.4  움짤 설정"]),
        ("4.", "행사 당일 운영", ["4.1  운영 흐름", "4.2  손님 안내 문구", "4.3  방치 자동 복귀",
                             "4.4  저장되는 파일"]),
        ("5.", "QR 코드의 수명", ["5.1  언제까지 받을 수 있나", "5.2  종료 시 주의"]),
        ("6.", "문제 해결", ["6.1  일반 오류 대처", "6.2  자주 묻는 질문"]),
    ]
    for ch, title, subs in toc:
        story.append(KeepTogether([P(f"<font color='#4C7DFF'><b>{ch}</b></font>  {title}", "toc_ch"),
                                   *[P("  ·  " + s, "toc_s") for s in subs], sp(4)]))
    story.append(PageBreak())

    # ── 1장 ──
    story.append(KeepTogether([
        section_header("1.", "설치 및 최초 실행"), sp(10),
        subsection_header("1.1", "시스템 요구사항"), sp(4),
        make_table(["항목", "요구사항", "비고"], [
            ["운영체제", "Windows 10 이상 (64비트)", "Windows 11 권장"],
            ["카메라", "USB 웹캠 (UVC 표준)", "미러리스+HDMI 캡처카드도 동일하게 인식"],
            ["메모리", "8 GB 이상", "16 GB 권장 — 움짤 인코딩에 여유"],
            ["저장 공간", "프로그램 약 340 MB + 사진", "세션당 사진 약 1.7 MB + 움짤 1~5 MB"],
            ["네트워크", "손님 휴대폰이 접속할 Wi-Fi", "인터넷 회선은 불필요. PC 모바일 핫스팟으로 대체 가능"],
            ["관리자 권한", "불필요", ""],
        ], col_widths=[2.6 * cm, 5.5 * cm, TW - 8.1 * cm])]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("1.2", "압축 해제와 폴더 구조"), sp(6),
        P("배포 파일은 <b>SnapStamp.zip</b> 이다. 압축을 풀면 <b>SnapStamp</b> 폴더 하나가 나오고, "
          "그 안에는 <b>_internal 폴더 1개</b>와 <b>SnapStamp.exe 파일 1개</b>가 들어 있다. "
          "실행은 SnapStamp.exe를 더블클릭하면 되고, 사용 방식은 단일 실행 파일일 때와 완전히 동일하다."),
        sp(8),
        note_box("<b>주의</b>  exe 파일만 따로 빼내면 실행되지 않는다. <b>_internal 폴더가 항상 exe 옆에 "
                 "같이 있어야 한다.</b> 바탕화면에서 실행하고 싶다면 exe를 옮기지 말고 "
                 "<b>마우스 오른쪽 → 바로 가기 만들기</b>로 단축 아이콘만 옮긴다. "
                 "또한 압축 프로그램 안에서 바로 실행하지 말고 반드시 <b>폴더에 풀고 나서</b> 실행한다."),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([subsection_header("1.3", "최초 실행 절차"), sp(6)]))
    story.append(enum_step(1, "SnapStamp.exe 실행",
                           "더블클릭한다. 설치 절차는 없다. 창이 뜨기까지 1~2초가 걸린다."))
    story.append(enum_step(2, "Windows SmartScreen 처리",
                           "인터넷에서 받은 파일에 최초 1회 \"Windows에서 PC를 보호했습니다\" 경고가 표시될 수 있다. "
                           "차단이 아니라 경고이며 [추가 정보] → [실행]을 선택하면 통과된다. 이후에는 표시되지 않는다."))
    story.append(enum_step(3, "카메라 자동 연결 확인",
                           "좌측 상단 라이브 미리보기에 화면이 나오고 [연결됨] 표시가 켜지면 정상이다."))
    story.append(enum_step(4, "설정 확인 후 [촬영 시작]",
                           "레이아웃·브랜딩을 확인하고 우측 하단 [촬영 시작]을 누르면 손님 화면으로 전환된다."))
    story.append(sp(10))
    story.append(figure("01_setup.png",
                        "운영자 화면. 좌측에 라이브 미리보기와 현재 설정 요약, 우측에 사진 배치 편집기가 있다. "
                        "우측 하단 [촬영 시작]을 누르면 손님 화면으로 전환된다."))
    story.append(note_box("<b>행사 당일 첫 실행 금지</b>  프로그램은 서명이 없어 백신·SmartScreen이 최초 1회 "
                          "경고를 낼 수 있다. <b>행사 전날 운영 PC에서 미리 한 번 실행해 두면</b> 당일 이 과정이 생략된다."))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("1.4", "카메라 연결"), sp(6),
        P("USB 웹캠을 꽂으면 자동으로 인식·연결된다. 여러 대가 연결돼 있으면 설정 창에서 사용할 카메라를 "
          "고를 수 있고, 한 번 고른 카메라는 다음 실행에도 유지된다. "
          "연결이 끊기면 프로그램이 스스로 재연결을 시도하므로 케이블을 뽑았다 꽂을 필요는 없다."),
        sp(8),
        note_box("Windows 설정에서 <b>[개인 정보] → [카메라] → \"데스크톱 앱이 카메라에 액세스하도록 허용\"</b>이 "
                 "꺼져 있으면 화면이 검게 나온다. 켜져 있는지 먼저 확인한다."),
    ]))
    story.append(PageBreak())

    # ── 2장 ──
    story.append(KeepTogether([
        section_header("2.", "설정 — 사진 만들기"), sp(8),
        P("좌측 하단 <b>[설정]</b> 버튼을 누르면 설정 창이 열린다. 설정 창은 "
          "<b>일반 설정 · 브랜딩/색감 · 손님 받기 페이지</b> 세 개의 항목으로 나뉜다. "
          "바꾼 값은 우측 미리보기에 즉시 반영된다."),
        sp(10), subsection_header("2.1", "레이아웃 · 사진 배치"), sp(6),
        P("메인 화면 우측에서 완성본의 사진 배치를 고른다. 세로 4컷(인생4컷 스트립), 가로 2x2, 가로 1x4 등 "
          "11종의 프리셋이 있고, 하단·상단 문구 영역이 있는 형태와 아이돌 포토카드형도 포함된다. "
          "프리셋을 고른 뒤 사진 칸을 <b>드래그로 옮기고 우하단 모서리로 크기를 조절</b>할 수 있으며, "
          "직접 조정하면 목록에는 <b>사용자 지정</b>으로 표시된다."),
        sp(6),
        P("<b>[예시 내보내기]</b>를 누르면 각 레이아웃의 가이드 PNG가 폴더로 저장된다. "
          "이 위에 디자인을 얹고 사진 자리를 투명하게 뚫으면 나만의 프레임 템플릿이 된다."),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("2.2", "브랜딩 · 색감"), sp(6),
        make_table(["설정", "설명"], [
            ["배경색", "완성본 바탕색. 색상 견본을 클릭하거나 직접 지정"],
            ["문구", "완성본에 새길 행사명·문구. 비워두면 표시되지 않음"],
            ["문구 위치", "9방향(좌상 ~ 우하) 중 선택"],
            ["문구 크기", "% 가 아닌 <b>포인트(pt)</b> 단위로 지정. 완성본 폭에 맞춰 자동 축소됨"],
            ["날짜 표시", "촬영 날짜를 문구와 함께 넣을지 여부"],
            ["색감", "원본 · 따뜻하게 · 차갑게 · 필름 · 비비드 · 흑백 6종"],
        ], col_widths=[3.2 * cm, TW - 3.2 * cm])]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("2.3", "촬영 전 보정"), sp(6),
        P("밝기 · 대비 · 채도 · 선명도를 미리 조절해 둘 수 있다. 촬영된 모든 사진에 동일하게 적용되므로, "
          "행사장 조명이 어둡거나 색이 튈 때 미리 맞춰 두면 손님마다 손볼 필요가 없다. "
          "수치 영역은 가로 스크롤로 되어 있어 미리보기를 크게 유지한 채 조절할 수 있다."),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("2.4", "테스트 촬영과 미리보기"), sp(6),
        P("색감은 실제 사진 없이 가늠하기 어렵다. <b>[테스트 촬영]</b> 버튼을 누르면 그 자리에서 한 장을 찍어 "
          "미리보기 네 칸을 그 사진으로 채운다. 이후 색감·보정을 바꿀 때마다 결과가 즉시 반영되므로 "
          "실제 조명에서 색을 맞출 수 있다. 사진이 작아 보이면 <b>[사진 1장만 보기]</b>로 크게 확인한다."),
        sp(8),
        note_box("미리보기는 <b>사진이 빠진 완성본</b>과 같은 비율·같은 글자 크기로 그려진다. "
                 "즉 미리보기에서 보이는 문구 위치와 크기가 실제 결과물과 일치한다."),
    ]))
    story.append(PageBreak())

    # ── 3장 ──
    story.append(KeepTogether([
        section_header("3.", "설정 — 손님 전달"), sp(8),
        subsection_header("3.1", "전달 방식과 QR"), sp(6),
        P("완성된 사진은 <b>운영 PC 안의 작은 웹서버</b>를 통해 전달된다. 사진이 인터넷의 외부 저장소로 "
          "올라가지 않으므로 참가자의 초상이 외부로 나가지 않는다. "
          "손님은 같은 Wi-Fi에 접속한 뒤 완성 화면의 QR을 찍으면 사진과 움짤을 함께 받을 수 있다."),
        sp(6),
        P("완성 화면에는 QR이 <b>두 개</b> 표시된다. ① <b>Wi-Fi 연결</b> — 찍으면 부스 Wi-Fi에 자동 접속된다. "
          "② <b>사진·움짤 받기</b> — 수령 페이지로 이동한다. 손님에게는 \"① 먼저 찍고 ② 찍으세요\"로 안내한다."),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("3.2", "손님 수령 페이지 꾸미기"), sp(6),
        P("손님이 QR로 들어오는 페이지도 행사에 맞게 꾸밀 수 있다. 설정 창의 "
          "<b>[손님 받기 페이지]</b> 항목에서 지정한다."),
        make_table(["설정", "설명"], [
            ["배경색 · 글자색", "페이지 전체 색. 글자색은 배경에 맞춰 자동 대비 조정도 가능"],
            ["로고", "페이지 상단에 넣을 로고 이미지 파일"],
            ["행사 문구", "\"○○ 페스티벌 포토부스\" 같은 페이지 제목"],
        ], col_widths=[3.6 * cm, TW - 3.6 * cm])]))
    story.append(sp(10))
    story.append(figure("06_guestpage.png",
                        "손님이 QR로 접속했을 때 보이는 수령 페이지. 설정한 배경색·문구가 그대로 적용되며, "
                        "아래로 내리면 [사진 저장하기]와 [움짤 저장하기] 버튼이 있다."))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("3.3", "Wi-Fi 접속 안내"), sp(6),
        make_table(["방식", "설명"], [
            ["표시 안 함", "손님이 이미 같은 Wi-Fi에 있는 경우"],
            ["현재 Wi-Fi", "운영 PC가 접속 중인 공유기 정보를 안내"],
            ["모바일 핫스팟", "PC의 핫스팟을 켜고 그 SSID·비밀번호로 QR 생성. 공유기가 없는 야외 행사용"],
        ], col_widths=[3.2 * cm, TW - 3.2 * cm])]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("3.4", "움짤 설정"), sp(6),
        P("네 컷을 찍는 동안 셔터 직전의 짧은 순간을 함께 담아 <b>움직이는 4컷</b>을 만든다. "
          "인스타그램 등에 올리기 좋은 형태이며, 사진과 같은 QR에서 함께 받을 수 있다. "
          "설정 창에서 <b>켜기/끄기</b>와 <b>GIF / MP4</b> 형식을 고른다. "
          "움짤은 사진보다 조금 늦게 완성되므로, 완성 화면에는 그동안 \"움짤 만드는 중\" 문구가 표시되고 "
          "준비가 끝나면 \"모두 준비 완료\"로 바뀐다. 손님은 기다리지 않고 QR을 먼저 찍어도 된다."),
    ]))
    story.append(PageBreak())

    # ── 4장 ──
    story.append(KeepTogether([
        section_header("4.", "행사 당일 운영"), sp(8),
        subsection_header("4.1", "운영 흐름"), sp(6)]))
    story.append(enum_step(1, "대기 화면", "브랜드와 안내 문구가 뜬 채 카메라가 살아 있다. 손님이 오면 시작 버튼을 누른다."))
    story.append(enum_step(2, "준비 화면", "\"준비되면 버튼을 한 번 더 눌러 촬영을 시작하세요\"가 뜬다. "
                                        "손님이 자세를 잡을 시간을 주는 단계다."))
    store_desc = ("카운트다운(기본 3초) 후 촬영된다. 셔터 순간 화면이 흰색으로 번쩍이며, "
                  "상단에 0/4 → 4/4로 진행이 표시된다. 컷마다 버튼을 한 번씩 누른다.")
    story.append(enum_step(3, "네 컷 촬영", store_desc))
    story.append(enum_step(4, "완성 화면", "합성된 사진이 연출과 함께 나타나고 QR 두 개가 표시된다. "
                                        "손님이 사진을 받아 가면 버튼을 두 번 빠르게 눌러 다음 손님을 받는다."))
    story.append(sp(10))
    story.append(figure("02_attract.png",
                        "① 대기 화면. 브랜드와 안내 문구가 표시되고 우측에 라이브 카메라가 계속 살아 있다."))
    story.append(figure("03_ready.png",
                        "② 준비 화면. 상단에 진행(0/4)과 컷 미리보기 칸이 보이고, 하단에 다음 동작 안내가 나온다."))
    story.append(figure("04_countdown.png",
                        "③ 카운트다운. 숫자가 3 → 1로 줄고 0이 되면 촬영된다. 셔터 순간 화면이 흰색으로 번쩍인다."))
    story.append(figure("05_result.png",
                        "④ 완성 화면. 좌측에 완성된 4컷, 우측에 QR 두 개(① Wi-Fi 연결 → ② 사진·움짤 받기). "
                        "움짤이 아직 만들어지는 중이면 그 자리에 진행 문구가 표시된다."))
    story.append(sp(4))
    story.append(P("위 그림에서 카메라에 비친 장면은 촬영 장소 보호를 위해 흐리게 처리한 것이며, "
                   "실제 화면에서는 선명하게 표시된다.", "footnote"))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("4.2", "손님 안내 문구"), sp(6),
        P("기본 트리거는 <b>스페이스바</b>이며 설정에서 다른 키로 바꿀 수 있다. "
          "USB 아케이드 버튼을 연결하면 손님은 큰 버튼 하나만 누르면 된다. "
          "부스 앞에 다음 문구를 붙여 두면 안내가 거의 필요 없다."),
        sp(6),
        make_table(["순서", "안내"], [
            ["1", "버튼을 눌러 시작하세요"],
            ["2", "자세를 잡고 버튼을 한 번 더 — 3초 뒤 촬영됩니다"],
            ["3", "네 번 반복하면 사진이 완성됩니다"],
            ["4", "① Wi-Fi QR → ② 사진 QR 순서로 찍어 받아 가세요"],
        ], col_widths=[1.6 * cm, TW - 1.6 * cm])]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("4.3", "방치 자동 복귀"), sp(6),
        P("손님이 중간에 자리를 뜨면 프로그램이 스스로 대기 화면으로 돌아간다. 준비 화면과 촬영 중 각각 "
          "대기 시간을 설정할 수 있고, 돌아가기 직전에는 <b>\"N초 뒤 처음으로 돌아갑니다\"</b> 예고가 표시되어 "
          "촬영 중인 손님이 갑자기 초기화되어 놀라는 일이 없다. 완성 화면은 기본적으로 자동 복귀하지 않는다 "
          "(손님이 QR을 찍을 시간을 위해). 필요하면 자동으로 바꿀 수 있다."),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("4.4", "저장되는 파일"), sp(6),
        P("지정한 저장 폴더에는 <b>완성한 4컷 사진</b>과 <b>완성한 움짤</b> <b>두 가지만</b> 남는다. "
          "촬영 원본이나 작업 중 파일은 임시 폴더에서 처리되고 자동으로 정리되므로 폴더가 지저분해지지 않는다. "
          "파일 이름은 촬영 시각과 고유 번호로 지어져 겹치지 않는다."),
        sp(8),
        P("<b>용량 기준</b>  한 팀당 사진 약 1.7 MB + 움짤 1~5 MB. 100팀을 받아도 1 GB 미만이다.", "footnote"),
    ]))
    story.append(PageBreak())

    # ── 5장 ──
    story.append(KeepTogether([
        section_header("5.", "QR 코드의 수명"), sp(8),
        subsection_header("5.1", "언제까지 받을 수 있나"), sp(6),
        P("QR 링크는 <b>프로그램이 켜져 있는 동안 계속 유효하다.</b> 손님마다 서로 다른 주소가 발급되고 "
          "이전 손님의 링크가 밀려나거나 덮어써지지 않는다. 즉 <b>몇 번째 손님이든, 처음 찍은 손님이 "
          "행사 마지막에 QR을 찍어도 사진을 받을 수 있다.</b> 받을 수 있는 사진 개수에 제한은 없다."),
        sp(8),
        P("연속 300회 세션을 돌린 시험에서 267건의 링크 전부가 마지막 시점까지 정상 동작했고, "
          "프로그램을 껐다 켠 뒤에도 이전 QR이 계속 동작하는 것을 확인했다.", "footnote"),
    ]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("5.2", "종료 시 주의"), sp(6),
        P("링크가 끊기는 경우는 두 가지뿐이다."),
        make_table(["상황", "결과"], [
            ["프로그램 종료", "그때까지 나눠 준 QR이 모두 동작하지 않게 된다"],
            ["저장 폴더에서 파일 삭제", "해당 손님의 사진만 받을 수 없게 된다"],
        ], col_widths=[5.0 * cm, TW - 5.0 * cm]),
        sp(8),
        note_box("<b>행사 중에는 프로그램을 끄지 않는다.</b> 종료할 때 경고가 표시되며, "
                 "아직 사진을 받아 가지 않은 손님이 있는지 확인한 뒤 종료한다. "
                 "사진 파일 자체는 저장 폴더에 그대로 남으므로, 나중에 따로 전달할 수 있다."),
    ]))
    story.append(PageBreak())

    # ── 6장 ──
    story.append(KeepTogether([
        section_header("6.", "문제 해결"), sp(8),
        subsection_header("6.1", "일반 오류 대처"), sp(4),
        make_table(["증상", "원인", "조치"], [
            ["실행이 안 됨", "exe만 따로 옮김", "_internal 폴더와 같은 자리에 두고 실행. 바로 가기를 사용"],
            ["백신이 차단", "서명 없는 프로그램 오탐", "차단 해제 후 예외 등록. 행사 전날 미리 실행해 확인"],
            ["화면이 검음", "카메라 권한 꺼짐", "Windows 설정 → 개인 정보 → 카메라 → 데스크톱 앱 허용"],
            ["카메라 인식 안 됨", "다른 프로그램이 사용 중", "화상회의 앱 등을 종료 후 재실행"],
            ["QR을 찍어도 안 열림", "손님이 다른 Wi-Fi에 있음", "먼저 Wi-Fi QR로 부스 Wi-Fi에 접속시킨다"],
            ["움짤이 안 생김", "설정에서 꺼져 있음", "설정 창에서 움짤 켜기 확인"],
            ["버튼을 눌러도 반응 없음", "다른 창이 앞에 있음", "SnapStamp 화면을 한 번 클릭해 앞으로 가져온다"],
        ], col_widths=[3.6 * cm, 3.6 * cm, TW - 7.2 * cm])]))
    story.append(sp(12))

    story.append(KeepTogether([
        subsection_header("6.2", "자주 묻는 질문"), sp(6),
        P("<b>Q. 사진이 인터넷 어딘가로 올라가나요?</b><br/>"
          "A. 아니다. 사진은 운영 PC 안에만 저장되고, 같은 Wi-Fi에 있는 손님 휴대폰으로만 전달된다. "
          "외부 서버로 전송되지 않으며 제작자에게도 아무 정보가 가지 않는다."),
        sp(6),
        P("<b>Q. 인터넷이 없는 야외에서도 되나요?</b><br/>"
          "A. 된다. PC의 모바일 핫스팟을 켜고 설정에서 핫스팟 방식을 고르면, 손님은 그 핫스팟에 접속해 받는다."),
        sp(6),
        P("<b>Q. 몇 팀까지 연속으로 받을 수 있나요?</b><br/>"
          "A. 300회 연속 시험에서 실패가 없었고 메모리도 늘지 않았다. 하루 행사 분량은 문제없다."),
        sp(6),
        P("<b>Q. 프린터로 뽑을 수 있나요?</b><br/>"
          "A. 현재 버전은 QR 전달만 지원한다. 실물 프린터 연동은 다음 버전에서 다룬다."),
        sp(6),
        P("<b>Q. DSLR을 연결할 수 있나요?</b><br/>"
          "A. 현재 버전은 USB 웹캠 방식이다. HDMI 캡처카드를 쓰면 미러리스 화면도 웹캠으로 인식되어 사용할 수 있다. "
          "카메라 직접 제어는 다음 버전에서 다룬다."),
    ]))
    story.append(sp(16))

    story.append(make_table(["제작", "정보"], [
        ["제작", "Unknown"],
        ["유튜브", "https://www.youtube.com/@unknown8563"],
        ["버전", "SnapStamp BETA Ver-0.1"],
    ], col_widths=[3.0 * cm, TW - 3.0 * cm]))

    # 프로젝트 루트에 생성한다(특정 PC 경로를 소스에 박지 않는다).
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = os.path.join(root, "SnapStamp 실행 안내서 (BETA Ver-0.1).pdf")
    doc = SimpleDocTemplate(out, pagesize=A4,
                            leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                            title="SnapStamp 실행 안내서 (BETA Ver-0.1)",
                            author="Unknown", subject="이벤트 포토부스 실행 안내서")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print("생성 완료:", out)


if __name__ == "__main__":
    build()
