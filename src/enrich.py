# 파싱된 거래에 yfinance 시세·섹터·수익률을 붙이는 인리치 모듈
import sys
from datetime import datetime, timedelta

from parse import Transaction

# yfinance는 선택 의존 — 미설치 시 인리치 스킵
try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False


def _yf_symbol(ticker: str) -> str:
    """PTR 티커 표기를 yfinance 심볼로 변환 (BRK.B → BRK-B)."""
    return ticker.replace(".", "-")


def _close_on_or_after(hist, date: datetime):
    """해당 날짜 이후 첫 거래일 종가를 반환 (없으면 None)."""
    after = hist[hist.index.date >= date.date()]
    if len(after):
        return float(after["Close"].iloc[0])
    return None


def enrich_transactions(txns: list[Transaction], year: int) -> None:
    """거래 목록에 섹터·진입가·현재가·수익률을 in-place로 채운다.

    수익률 정의 (가이드 §6): 공시일(일반인 추종 가능 최초 시점) 종가 진입 → 현재가.
    주식([ST])만 대상. 티커별로 한 번씩 조회해 캐시.
    """
    if not _HAS_YF:
        print("  ! yfinance 미설치 — 인리치 스킵", file=sys.stderr)
        return

    # 인리치 대상: 티커 있고 주식인 거래
    targets = [t for t in txns if t.ticker and t.asset_type == "stock"]
    symbols = sorted({t.ticker for t in targets})
    print(f"  인리치: 고유 티커 {len(symbols)}개 조회", file=sys.stderr)

    cache: dict[str, dict] = {}
    for tk in symbols:
        try:
            tobj = yf.Ticker(_yf_symbol(tk))
            hist = tobj.history(period="2y", auto_adjust=True)
            info = tobj.info if hasattr(tobj, "info") else {}
            cache[tk] = {
                "hist": hist,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "current": (float(hist["Close"].iloc[-1]) if len(hist) else None),
            }
        except Exception as e:
            print(f"    ! yfinance {tk}: {e}", file=sys.stderr)
            cache[tk] = {}

    for t in targets:
        c = cache.get(t.ticker, {})
        hist = c.get("hist")
        t.sector = c.get("sector")
        t.industry = c.get("industry")
        t.current_price = c.get("current")
        if hist is not None and len(hist) and t.notification_date:
            try:
                nd = datetime.strptime(t.notification_date, "%m/%d/%Y")
                entry = _close_on_or_after(hist, nd)
                t.entry_price = entry
                if entry and t.current_price:
                    ret = (t.current_price - entry) / entry
                    # 매도는 부호 반전 (판 뒤 하락하면 이득)
                    t.return_pct = round(100 * (ret if t.type == "buy" else -ret), 2)
            except ValueError:
                pass


if __name__ == "__main__":
    # 단독 실행: 기존 JSON을 읽어 인리치 후 덮어쓰기
    import json
    from dataclasses import asdict, fields
    from config import DATA_DIR

    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    path = DATA_DIR / f"ptr_{yr}.json"
    recs = json.load(open(path, encoding="utf-8"))
    valid = {f.name for f in fields(Transaction)}
    txns = [Transaction(**{k: v for k, v in r.items() if k in valid}) for r in recs]
    enrich_transactions(txns, yr)
    path.write_text(
        json.dumps([asdict(t) for t in txns], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    enriched = sum(1 for t in txns if t.return_pct is not None)
    print(f"인리치 완료: 수익률 계산 {enriched}건 / 전체 {len(txns)}건")
