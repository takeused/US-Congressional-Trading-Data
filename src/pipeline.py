# 인덱스→PDF→텍스트→파싱→(선택)인리치를 순차 실행하는 배치 파이프라인
import argparse
import json
import sys
from dataclasses import asdict

from config import DATA_DIR, ensure_dirs
from fetch_index import fetch_ptr_filings
from fetch_pdf import fetch_pdf
from extract import extract_text, ScannedPdfError
from parse import parse_text, Transaction


def run(year: int, *, limit: int | None = None, do_enrich: bool = False) -> dict:
    """연도별 PTR 파이프라인을 실행하고 요약 통계를 반환한다."""
    ensure_dirs()
    filings = fetch_ptr_filings(year)
    if limit:
        filings = filings[:limit]

    print(f"[{year}] PTR 공시 {len(filings)}건 처리 시작", file=sys.stderr)

    all_txns: list[Transaction] = []
    stats = {"filings": len(filings), "scanned": 0, "download_err": 0, "parse_err": 0}

    for n, f in enumerate(filings, 1):
        try:
            pdf = fetch_pdf(year, f.doc_id)
        except Exception as e:  # 네트워크·404 등
            stats["download_err"] += 1
            print(f"  ! download {f.doc_id}: {e}", file=sys.stderr)
            continue
        try:
            text = extract_text(pdf)
        except ScannedPdfError:
            stats["scanned"] += 1  # 스캔 PDF → 스킵 (OCR 미도입)
            continue
        except Exception as e:
            stats["parse_err"] += 1
            print(f"  ! extract {f.doc_id}: {e}", file=sys.stderr)
            continue

        filer = f"{f.first} {f.last}".strip()
        txns = parse_text(text, filer=filer, state_dst=f.state_dst, doc_id=f.doc_id)
        all_txns.extend(txns)
        if n % 50 == 0:
            print(f"  ... {n}/{len(filings)} (거래 {len(all_txns)}건)", file=sys.stderr)

    if do_enrich:
        from enrich import enrich_transactions
        enrich_transactions(all_txns, year)

    records = [asdict(t) for t in all_txns]
    out = DATA_DIR / f"ptr_{year}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    stats["transactions"] = len(records)
    stats["with_ticker"] = sum(1 for r in records if r["ticker"])
    stats["null_ticker_pct"] = round(
        100 * (1 - stats["with_ticker"] / len(records)) if records else 0, 1
    )
    stats["output"] = str(out)
    print(f"[{year}] 완료: {json.dumps(stats, ensure_ascii=False)}", file=sys.stderr)
    return stats


def main():
    ap = argparse.ArgumentParser(description="미 하원 PTR 매매 데이터 파이프라인")
    ap.add_argument("--year", type=int, required=True, help="대상 연도 (예: 2026)")
    ap.add_argument("--limit", type=int, default=None, help="처리할 공시 수 제한 (테스트용)")
    ap.add_argument("--enrich", action="store_true", help="yfinance 시세·섹터 인리치 실행")
    args = ap.parse_args()
    run(args.year, limit=args.limit, do_enrich=args.enrich)


if __name__ == "__main__":
    main()
