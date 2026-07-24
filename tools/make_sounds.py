"""포토부스 효과음 생성(WAV). 부드러운 카운트다운 비프 + 진짜 카메라 셔터 '찰칵' + 완료음."""
import math
import random
import struct
import wave
from pathlib import Path

OUT = Path("assets/sounds")
OUT.mkdir(parents=True, exist_ok=True)
RATE = 44100
random.seed(7)


def _write(name, samples):
    with wave.open(str(OUT / name), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


def _bell(freq, ms, vol=0.4, decay=6.0):
    """종소리 같은 부드러운 톤(빠른 어택 + 지수 감쇠) — 싼티 안 나는 비프."""
    n = int(RATE * ms / 1000)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-decay * (i / n))
        atk = min(1.0, i / (RATE * 0.004))  # 4ms 어택
        s = math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * freq * 2 * t)
        out.append(vol * atk * env * s)
    return out


def _clack(ms, vol, lp=0.55, res=(180, 90), decay=22.0):
    """기계식 셔터 '클랙' — 저역통과(lowpass)한 노이즈 몸통 + 짧게 감쇠하는 저역 공진(punch).
    저역통과로 '히스'가 아닌 '톡/툭' 질감을 만들고, 감쇠 공진으로 몸집을 준다(순수 톤 아님)."""
    n = int(RATE * ms / 1000)
    out = []
    prev = 0.0
    for i in range(n):
        env = math.exp(-decay * (i / n))
        white = random.random() * 2 - 1
        prev = prev + lp * (white - prev)      # 1극 저역통과 → 부드러운 몸통
        body = prev
        # 저역 공진 몇 개(빠르게 감쇠) → 기계식 punch. 톤처럼 지속되지 않게 감쇠 큼.
        pr = sum(math.sin(2 * math.pi * f * i / RATE) for f in res) * math.exp(-45 * (i / n))
        out.append(vol * env * (body * 1.4 + pr * 0.35))
    return out


def _normalize(samples, peak=0.97):
    m = max((abs(s) for s in samples), default=1.0) or 1.0
    g = peak / m
    return [s * g for s in samples]


def _rms(samples):
    return (sum(s * s for s in samples) / max(1, len(samples))) ** 0.5


def generate():
    # 카운트다운: 부드러운 벨톤 — 작고 짧게(셔터가 훨씬 크게 들리도록 대비).
    _write("beep.wav", _bell(680, 150, vol=0.18, decay=8.0))
    # 완료음: 밝은 상승 3음 벨.
    _write("done.wav", _bell(660, 130, 0.32) + _bell(880, 130, 0.34) + _bell(1175, 240, 0.38))
    # ⚠️ shutter.wav 는 실제 녹음 음원(Mixkit "Camera shutter hard click", 무료 라이선스,
    # 끝부분 컷)으로 교체됨 → 합성으로 덮어쓰지 않는다. 출처: assets/sounds/CREDITS.txt
    print("wrote beep.wav, done.wav (shutter.wav = 실제 음원, 유지)")


if __name__ == "__main__":
    generate()
