# pdftotext -layout로 PTR PDF에서 레이아웃 보존 텍스트를 추출하는 모듈
import subprocess
from pathlib import Path

# 텍스트가 이보다 짧으면 스캔(이미지) PDF로 간주 (가이드 §3)
MIN_TEXT_LEN = 50


class ScannedPdfError(Exception):
    """pdftotext 결과가 거의 비어 있는 스캔 PDF."""


def extract_text(pdf: Path) -> str:
    """pdftotext -layout로 텍스트를 추출한다.

    거의 빈 결과면 ScannedPdfError를 던진다(OCR fallback 대상).
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    txt = result.stdout
    if len(txt.strip()) < MIN_TEXT_LEN:
        raise ScannedPdfError(f"scanned/empty PDF: {pdf.name}")
    return txt


if __name__ == "__main__":
    import sys

    from config import PDF_CACHE_DIR

    yr = sys.argv[1] if len(sys.argv) > 1 else "2026"
    doc = sys.argv[2] if len(sys.argv) > 2 else "20034201"
    p = PDF_CACHE_DIR / yr / f"{doc}.pdf"
    print(extract_text(p))
