# pdftotext 출력에서 PTR 거래 한 줄씩을 정규식으로 파싱하는 모듈
import re
from dataclasses import dataclass

from config import ASSET_TYPE, TXN_KIND

# 거래유형(S/P/E) + (선택)(partial) 수식어 + 거래일 + 공시일 + 금액구간
# 실제 PDF는 "S (partial)  03/16/2026 03/16/2026 $1,001 - $15,000" 형태도 있음
TXN_RE = re.compile(
    r"\b([SPE])\s+(?:\([^)]*\)\s+)?"
    r"(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+"
    r"(\$[\d,]+(?:\.\d+)?(?:\s*-\s*\$[\d,]+(?:\.\d+)?)?)"
)

# 티커: 괄호 안 2~7자 대문자/숫자 (CUSIP 9자·소문자 수식어는 제외됨)
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)")
# 거래소 접두 형식: "NYSEARCA: DIA", "NASDAQ: QQQ" 등
EXCH_TICKER_RE = re.compile(r"(?:NYSE|NYSEARCA|NASDAQ|BATS|AMEX|OTC)\s*:\s*([A-Z][A-Z0-9.\-]{0,6})")
# 자산유형 코드 [ST]/[OP]/[MF]/[GS] 등
ASSET_CODE_RE = re.compile(r"\[([A-Z]{2})\]")
# 소유자 표시 (라인 시작의 SP/JT/DC)
OWNER_RE = re.compile(r"^\s*(SP|JT|DC)\b")
# 설명 블록 마커 (F: filing status, S: subholding, O: owner, D: description)
DESC_MARKER_RE = re.compile(r"^\s*[FSOD]\s+.*:")


@dataclass
class Transaction:
    """PTR 거래 한 건."""
    filer: str = ""
    state_dst: str = ""
    doc_id: str = ""
    ticker: str | None = None
    asset_type: str | None = None
    owner: str | None = None
    type: str = ""              # buy / sell / exchange
    amount: str = ""           # 금액구간 원문
    transaction_date: str = ""
    notification_date: str = ""
    # 인리치 단계(enrich.py)에서 채워지는 필드
    sector: str | None = None
    industry: str | None = None
    entry_price: float | None = None      # 공시일 종가 진입가
    current_price: float | None = None
    return_pct: float | None = None       # 공시일→현재 수익률(%)


def _complete_amount(amount: str, lines: list[str], i: int) -> str:
    """금액 상한이 다음 줄로 잘린 경우 결합한다 (가이드 §5)."""
    if amount.count("$") >= 2:
        return amount
    if not amount.rstrip().endswith("-"):
        return amount
    for j in range(i + 1, min(i + 3, len(lines))):
        um = re.search(r"\$[\d,]+(?:\.\d+)?", lines[j])
        if um:
            return amount.rstrip(" -") + " - " + um.group(0)
    return amount


def _find_ticker_and_code(lines: list[str], i: int, pre: str) -> tuple[str | None, str | None]:
    """거래행 이전 텍스트 + 연속 이어지는 줄에서 티커와 자산코드를 찾는다.

    자산명·티커는 다음 줄로 줄바꿈되지만, 설명 블록(F/S/O/D:)이나 빈 줄이
    나오면 멈춘다 — 설명 서술에 나열된 다른 티커가 오염되는 것을 막는다.
    """
    parts = [pre]
    for j in range(i + 1, len(lines)):
        ln = lines[j]
        if not ln.strip():  # 빈 줄 = 항목 경계
            break
        if DESC_MARKER_RE.match(ln):  # 설명 블록 시작
            break
        parts.append(ln)
    window = " ".join(parts)

    tick_m = TICKER_RE.search(window) or EXCH_TICKER_RE.search(window)
    code_m = ASSET_CODE_RE.search(window)
    ticker = tick_m.group(1) if tick_m else None
    code = ASSET_TYPE.get(code_m.group(1)) if code_m else None
    return ticker, code


def parse_text(text: str, *, filer: str = "", state_dst: str = "", doc_id: str = "") -> list[Transaction]:
    """레이아웃 텍스트에서 거래 목록을 추출한다."""
    lines = text.splitlines()
    txns: list[Transaction] = []
    for i, line in enumerate(lines):
        m = TXN_RE.search(line)
        if not m:
            continue
        typ, tdate, ndate, amt = m.groups()
        amt = _complete_amount(amt, lines, i)
        pre = line[: m.start()]  # 거래유형 앞부분 = 자산명 조각
        owner_m = OWNER_RE.search(line)
        ticker, code = _find_ticker_and_code(lines, i, pre)

        # 엣지케이스 4: 거래일 > 공시일이면 필러 오타로 보고 제외 (가이드 §5)
        if _to_ord(tdate) > _to_ord(ndate):
            continue

        txns.append(
            Transaction(
                filer=filer,
                state_dst=state_dst,
                doc_id=doc_id,
                ticker=ticker,
                asset_type=code,
                owner=owner_m.group(1) if owner_m else None,
                type=TXN_KIND[typ],
                amount=re.sub(r"\s+", " ", amt).strip(),
                transaction_date=tdate,
                notification_date=ndate,
            )
        )
    return txns


def _to_ord(mdY: str) -> int:
    """MM/DD/YYYY를 정렬 가능한 정수로 (비교 전용)."""
    mm, dd, yy = mdY.split("/")
    return int(yy) * 10000 + int(mm) * 100 + int(dd)


if __name__ == "__main__":
    import sys

    from extract import extract_text
    from config import PDF_CACHE_DIR

    yr = sys.argv[1] if len(sys.argv) > 1 else "2026"
    doc = sys.argv[2] if len(sys.argv) > 2 else "20034201"
    txt = extract_text(PDF_CACHE_DIR / yr / f"{doc}.pdf")
    for t in parse_text(txt, doc_id=doc):
        print(t)
