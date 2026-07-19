# 스캔(이미지) PDF를 PyMuPDF 렌더 + RapidOCR로 텍스트화하는 fallback 모듈
import sys
from pathlib import Path

import fitz  # PyMuPDF

# RapidOCR 엔진은 무겁게 한 번만 초기화 (지연 로딩)
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _reconstruct_lines(ocr_result, y_tol: float = 10.0) -> str:
    """OCR 박스들을 y좌표로 행 클러스터링해 레이아웃 텍스트로 복원한다.

    RapidOCR 결과: [[box(4점), text, score], ...]
    같은 행(y가 가까움)은 x순으로 정렬해 공백으로 잇는다.
    """
    if not ocr_result:
        return ""
    items = []
    for box, text, _score in ocr_result:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / 4, min(xs), text))
    items.sort(key=lambda t: (t[0], t[1]))

    lines: list[list[tuple[float, str]]] = []
    cur_y = None
    for yc, xl, text in items:
        if cur_y is None or abs(yc - cur_y) > y_tol:
            lines.append([])
            cur_y = yc
        lines[-1].append((xl, text))
    out = []
    for row in lines:
        row.sort(key=lambda t: t[0])
        out.append("  ".join(t for _x, t in row))
    return "\n".join(out)


def ocr_pdf(pdf: Path, *, zoom: float = 3.0) -> str:
    """스캔 PDF 전체 페이지를 OCR해 레이아웃 복원 텍스트를 반환한다."""
    engine = _get_engine()
    doc = fitz.open(pdf)
    pages_text = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        result, _elapse = engine(pix.tobytes("png"))
        pages_text.append(_reconstruct_lines(result))
    doc.close()
    return "\n".join(pages_text)


if __name__ == "__main__":
    from config import PDF_CACHE_DIR

    yr = sys.argv[1] if len(sys.argv) > 1 else "2026"
    doc = sys.argv[2] if len(sys.argv) > 2 else "8221321"
    print(ocr_pdf(PDF_CACHE_DIR / yr / f"{doc}.pdf"))
