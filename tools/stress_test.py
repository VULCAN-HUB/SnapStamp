"""SnapStamp 연속 사용 스트레스 테스트 — 50회 이상 세션을 다양한 조건으로 돌리며
정상 동작과 기기 부담(메모리·스레드·핸들·디스크)을 함께 측정한다.

실행: QT_QPA_PLATFORM=offscreen python tools/stress_test.py [횟수]
"""
import ctypes
import ctypes.wintypes as wt
import gc
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from app.controller import AppController          # noqa: E402
from app.state import AppState                    # noqa: E402
from config import load_config                    # noqa: E402


# ── 기기 부담 측정(psutil 없이 Windows API로) ───────────────────────────
class _PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_k32.GetCurrentProcess.restype = wt.HANDLE
_psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
_psapi.GetProcessMemoryInfo.restype = wt.BOOL
_k32.GetProcessHandleCount.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
_k32.GetProcessHandleCount.restype = wt.BOOL


def rss_mb(peak=False):
    pmc = _PMC(); pmc.cb = ctypes.sizeof(_PMC)
    if not _psapi.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return -1.0
    return (pmc.PeakWorkingSetSize if peak else pmc.WorkingSetSize) / 1e6


def handles():
    n = wt.DWORD()
    if not _k32.GetProcessHandleCount(_k32.GetCurrentProcess(), ctypes.byref(n)):
        return -1
    return int(n.value)


def folder_mb(p):
    try:
        return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) / 1e6
    except Exception:
        return 0.0


def snapshot(tag, save, work):
    return {"tag": tag, "rss": round(rss_mb(), 1), "threads": threading.active_count(),
            "handles": handles(), "save_mb": round(folder_mb(save), 1),
            "work_files": len(list(Path(work).glob("*"))) if Path(work).exists() else 0}


# ── 세션 1회 ────────────────────────────────────────────────────────────
def run_session(c, abandon_after=0):
    """abandon_after>0 이면 그 컷까지만 찍고 중도 이탈(방치) 시나리오."""
    c.begin_session()
    shots = abandon_after if abandon_after else 4
    for _ in range(shots):
        for _ in range(18):
            c._pump_frame()
        c._set(AppState.COUNTDOWN)
        c.capture_current()
    if abandon_after:
        c.discard_session()
        return None
    t0 = time.time()
    while time.time() - t0 < 60 and c.state != AppState.RESULT:
        app.processEvents(); time.sleep(0.02)
    return c.final_path


def wait_gif(c, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if c.gif_worker is None or not c.gif_worker.isRunning():
            return True
        app.processEvents(); time.sleep(0.03)
    return False


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 55
    save = tempfile.mkdtemp(prefix="snapstress_")
    cfg = load_config()
    cfg["camera"] = {"backend": "mock", "device_index": 0, "device_name": ""}
    cfg["save_path"] = save
    cfg["share_port"] = 8790
    c = AppController(cfg, save)

    urls = []
    orig = c._on_delivered
    c._on_delivered = lambda fp, url, mode: (urls.append(url), orig(fp, url, mode))

    from core.layouts import LAYOUTS
    layouts = list(LAYOUTS.keys())
    tones = ["원본", "따뜻하게", "필름", "흑백", "비비드"]

    marks = [snapshot("start", save, c.work_dir)]
    durations, fails, abandons = [], [], 0
    print(f"연속 {total}회 세션 시작 (저장: {save})\n")

    for i in range(1, total + 1):
        # 다양한 조건으로 돌린다(레이아웃·색감·보정·거울·움짤·브랜딩)
        cfg["slots"] = LAYOUTS[layouts[i % len(layouts)]]["slots"]
        cfg["canvas_size"] = list(LAYOUTS[layouts[i % len(layouts)]]["canvas_size"])
        cfg["tone"] = tones[i % len(tones)]
        cfg["adjust"] = {"brightness": (i % 5) * 10, "contrast": (i % 3) * 10,
                         "saturation": 0, "sharpness": 0}
        cfg["mirror_preview"] = (i % 7 == 0)
        cfg["gif_enabled"] = (i % 4 != 0)          # 4회마다 움짤 끔
        cfg["gif_format"] = "MP4" if i % 10 == 0 else "GIF"
        cfg["brand_text"] = f"TEST {i}" if i % 2 else ""
        cfg["brand_show_date"] = (i % 3 == 0)
        cfg["keep_cuts"] = (i % 11 == 0)

        if i % 9 == 0:                              # 중도 이탈 시나리오
            t0 = time.time(); run_session(c, abandon_after=(i % 3) + 1)
            abandons += 1; durations.append(time.time() - t0)
        else:
            t0 = time.time()
            fp = run_session(c)
            wait_gif(c)
            durations.append(time.time() - t0)
            if not fp or not Path(fp).exists():
                fails.append((i, "합성 결과 없음"))
        if i % 10 == 0:
            gc.collect()
            marks.append(snapshot(f"{i}회", save, c.work_dir))
            m = marks[-1]
            print(f"  {i:3d}회  메모리 {m['rss']:7.1f}MB  스레드 {m['threads']:2d}  "
                  f"핸들 {m['handles']:4d}  저장 {m['save_mb']:6.1f}MB  임시 {m['work_files']}개"
                  f"  세션평균 {sum(durations[-10:])/len(durations[-10:]):.2f}s")

    # ── 검증 ────────────────────────────────────────────────────────────
    print("\n[결과 검증]")
    print(f"  완료 세션        : {len(urls)}회 (중도이탈 {abandons}회 별도)")
    print(f"  실패             : {len(fails)}건 {fails[:3]}")
    stems = {Path(u.rsplit('/', 1)[-1]).stem for u in urls}
    print(f"  세션명 중복 없음 : {len(stems) == len(urls)}")

    # 저장 폴더: 세션당 사진+움짤(움짤 끈 회차는 사진만)
    files = [f for f in Path(save).iterdir() if f.is_file()]
    jpg = [f for f in files if f.suffix == ".jpg"]
    mot = [f for f in files if f.suffix in (".gif", ".mp4")]
    print(f"  저장 파일        : 사진 {len(jpg)} · 움짤 {len(mot)} (그 외 {len(files)-len(jpg)-len(mot)})")

    # 첫 번째와 마지막 링크가 모두 살아있는지(= 앞 손님 링크 유지)
    alive = 0
    for u in (urls[0], urls[len(urls)//2], urls[-1]):
        try:
            body = urllib.request.urlopen(u, timeout=5).read()
            if b"<!doctype html>" in body[:200].lower() or b"<html" in body[:200].lower():
                alive += 1
        except Exception as e:
            print(f"    링크 실패: {u} -> {e}")
    print(f"  링크 생존(처음/중간/끝) : {alive}/3")

    # ── 전체 링크 일제 점검: 운영 중 QR로 실제 받을 수 있는 최대 장수 ──
    # 페이지(HTML)만이 아니라 그 안의 사진 파일까지 실제로 내려받아 본다.
    ok_page = ok_file = 0
    dead = []
    for i, u in enumerate(urls, 1):
        try:
            html = urllib.request.urlopen(u, timeout=5).read().decode("utf-8", "replace")
            ok_page += 1
        except Exception as e:
            dead.append((i, "페이지", str(e)[:60])); continue
        stem = u.rstrip("/").rsplit("/", 1)[-1]
        try:
            data = urllib.request.urlopen(u.split("/p/")[0] + f"/{stem}.jpg", timeout=5).read()
            if data[:2] == b"\xff\xd8" and len(data) > 10000:   # 실제 JPEG인지
                ok_file += 1
            else:
                dead.append((i, "사진", f"손상 {len(data)}B"))
        except Exception as e:
            dead.append((i, "사진", str(e)[:60]))
    print(f"  전체 링크 재접속      : 페이지 {ok_page}/{len(urls)} · 사진 실다운로드 {ok_file}/{len(urls)}")
    # cp949 콘솔에서 em-dash 같은 문자는 UnicodeEncodeError를 낸다. ASCII 기호만 쓴다.
    print(f"  -> 운영 중 QR로 받을 수 있는 사진: {ok_file}장 "
          f"({'제한 없음(전 회차 생존)' if ok_file == len(urls) else '일부 소실'})")
    if dead:
        print(f"    소실 {len(dead)}건 (앞 5개): {dead[:5]}")
    alive_all = (ok_file == len(urls))

    marks.append(snapshot("end", save, c.work_dir))
    s, e = marks[0], marks[-1]
    print("\n[기기 부담]")
    print(f"  메모리 : {s['rss']:.1f}MB → {e['rss']:.1f}MB  (증가 {e['rss']-s['rss']:+.1f}MB)"
          f"  · 최대치 {rss_mb(peak=True):.1f}MB")
    print(f"  스레드 : {s['threads']} → {e['threads']}  (증가 {e['threads']-s['threads']:+d})")
    print(f"  핸들   : {s['handles']} → {e['handles']}  (증가 {e['handles']-s['handles']:+d})")
    print(f"  임시파일: {s['work_files']} → {e['work_files']}개")
    print(f"  저장폴더: {e['save_mb']:.1f}MB / {len(files)}개 파일 "
          f"(세션당 평균 {e['save_mb']/max(1,len(urls)):.2f}MB)")
    print(f"  세션 소요: 평균 {sum(durations)/len(durations):.2f}s "
          f"· 최대 {max(durations):.2f}s · 최소 {min(durations):.2f}s")

    c.shutdown()
    app.processEvents()
    print(f"\n  종료 후 스레드 : {threading.active_count()}  핸들 {handles()}")
    shutil.rmtree(save, ignore_errors=True)
    ok = not fails and alive == 3 and alive_all and len(stems) == len(urls)
    print("\n판정:", "정상 — 연속 사용 가능" if ok else "문제 발견(위 실패 항목 확인)")


if __name__ == "__main__":
    main()
