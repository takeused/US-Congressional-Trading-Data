# 스캔(이미지) PDF를 PyMuPDF 렌더 + RapidOCR로 텍스트화하는 fallback 모듈
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

_ZOOM = 3.0  # 렌더 배율 (OCR·픽셀분석 공통)

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


# ── 체크박스 그리드 픽셀 분석 (거래유형·금액) ──────────────────────
# RapidOCR은 격자 셀 안의 단독 X 표시를 텍스트로 탐지하지 못한다.
# 대신 헤더 앵커(PURCHASE/SALE/EXCHANGE)의 x좌표에서, 각 거래행 y밴드의
# 셀 어두운 픽셀 비율을 재 어느 칸에 X가 있는지 판정한다.
from parse import SCAN_DATE_RE, OWNER_RE, _scan_ticker, _norm_year  # noqa: E402

# 거래유형 3컬럼 앵커 검출 실패 시 기본값 (관측된 x, zoom=3 기준)
_TYPE_DEFAULT_X = {"buy": 1038.0, "sell": 1093.0, "exchange": 1149.0}
_DARK_THR = 128        # 이 밝기 미만이면 어두운 픽셀
_CELL_W, _CELL_H = 26, 30
_TYPE_DELTA = 0.045    # 컬럼 baseline 대비 이만큼 튀어야 표시로 인정
_TYPE_MARGIN = 0.02    # 최대 delta가 차순위보다 이만큼 앞서야 확신


def _page_gray(page) -> np.ndarray:
    """페이지를 그레이스케일 numpy 배열로 렌더."""
    pix = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM), colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _dark_ratio(img: np.ndarray, x: float, y: float) -> float:
    """(x,y) 중심 셀에서 어두운 픽셀 비율."""
    xi, yi = int(x), int(y)
    cell = img[max(0, yi - _CELL_H):yi + _CELL_H, max(0, xi - _CELL_W):xi + _CELL_W]
    if cell.size == 0:
        return 0.0
    return float((cell < _DARK_THR).mean())


def _type_anchors(items) -> dict[str, float]:
    """OCR 토큰에서 PURCHASE/SALE/EXCHANGE x앵커를 찾는다 (실패 시 기본값)."""
    anchors = {}
    for _yc, xc, text in items:
        t = text.strip().upper()
        if t == "PURCHASE":
            anchors["buy"] = xc
        elif t == "SALE":
            anchors["sell"] = xc
        elif t == "EXCHANGE":
            anchors["exchange"] = xc
    if len(anchors) == 3:
        return anchors
    return dict(_TYPE_DEFAULT_X)


def _classify_types(rows_ratios: list[dict[str, float]]) -> list[str]:
    """페이지 내 모든 행의 컬럼별 어두운 비율을 받아 baseline 차감으로 유형 판정.

    표 세로 테두리선은 모든 행에서 균일하게 어두워 baseline이 높다 → 차감 시 0.
    진짜 X는 그 컬럼의 미표시 행(=baseline) 대비 튀는 값으로 잡힌다.
    """
    if not rows_ratios:
        return []
    keys = ["buy", "sell", "exchange"]
    # 컬럼별 baseline = 하위 20% 분위(미표시 상태 근사)
    baseline = {}
    for k in keys:
        vals = sorted(r[k] for r in rows_ratios)
        baseline[k] = vals[max(0, len(vals) // 5 - 1)]
    out = []
    for r in rows_ratios:
        deltas = {k: r[k] - baseline[k] for k in keys}
        ordered = sorted(deltas.values(), reverse=True)
        best = max(deltas, key=deltas.get)
        if ordered[0] >= _TYPE_DELTA and (ordered[0] - ordered[1]) >= _TYPE_MARGIN:
            out.append(best)
        else:
            out.append("")  # 미상
    return out


def _cluster_rows(items, y_tol: float = 14.0):
    """OCR 토큰을 y로 행 클러스터링 (각 행: x정렬된 (xc,text) 리스트)."""
    items = sorted(items, key=lambda t: (t[0], t[1]))
    rows, cur_y = [], None
    for yc, xc, text in items:
        if cur_y is None or abs(yc - cur_y) > y_tol:
            rows.append((yc, []))
            cur_y = yc
        rows[-1][1].append((xc, text))
    for _y, r in rows:
        r.sort(key=lambda t: t[0])
    return rows


def extract_scanned_rows(pdf: Path) -> list[dict]:
    """스캔 양식에서 거래행을 추출 (텍스트 필드 + 픽셀 기반 거래유형)."""
    engine = _get_engine()
    doc = fitz.open(pdf)
    out: list[dict] = []
    for page in doc:
        img = _page_gray(page)
        result, _ = engine(page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM)).tobytes("png"))
        if not result:
            continue
        items = []
        for box, text, _score in result:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append((sum(ys) / 4, min(xs), text))
        anchors = _type_anchors(items)
        import re as _re
        # 1차: 거래행 수집 + 컬럼별 어두운 비율 측정
        page_rows, page_ratios = [], []
        for yc, row in _cluster_rows(items):
            line = "  ".join(t for _x, t in row)
            if "Example" in line or "MM" in line:
                continue
            dates = SCAN_DATE_RE.findall(line)
            if len(dates) < 2:
                continue
            first_pos = line.find(dates[0])
            asset_pre = line[:first_pos]
            asset = _re.sub(r"^\s*(SP|JT|DC)\b", "", asset_pre).strip(" \t-")
            if len(asset) < 3:
                continue
            owner_m = OWNER_RE.search(line)
            page_rows.append({
                "asset_name": asset or None,
                "ticker": _scan_ticker(asset_pre),
                "owner": owner_m.group(1) if owner_m else None,
                "transaction_date": _norm_year(dates[0]),
                "notification_date": _norm_year(dates[1]),
            })
            page_ratios.append({k: _dark_ratio(img, x, yc) for k, x in anchors.items()})
        # 2차: baseline 차감으로 유형 판정
        types = _classify_types(page_ratios)
        for r, ty in zip(page_rows, types):
            r["type"] = ty
            out.append(r)
    doc.close()
    return out


if __name__ == "__main__":
    from config import PDF_CACHE_DIR

    yr = sys.argv[1] if len(sys.argv) > 1 else "2026"
    doc = sys.argv[2] if len(sys.argv) > 2 else "8221321"
    if "--rows" in sys.argv:
        for r in extract_scanned_rows(PDF_CACHE_DIR / yr / f"{doc}.pdf"):
            print(f"  {r['type'] or '-':8} {str(r['ticker']):6} {r['transaction_date']} "
                  f"{r['notification_date']}  {(r['asset_name'] or '')[:38]}")
    else:
        print(ocr_pdf(PDF_CACHE_DIR / yr / f"{doc}.pdf"))
