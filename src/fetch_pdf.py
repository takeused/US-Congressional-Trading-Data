# DocID 기준으로 PTR PDF를 다운로드하고 로컬 캐시에 저장하는 모듈
import time
import urllib.request
from pathlib import Path

from config import UA, PTR_PDF_URL, PDF_CACHE_DIR, REQUEST_DELAY_SEC


def _cache_path(year: int, doc_id: str) -> Path:
    """캐시 파일 경로 (cache/pdf/{year}/{doc_id}.pdf)."""
    return PDF_CACHE_DIR / str(year) / f"{doc_id}.pdf"


def fetch_pdf(year: int, doc_id: str, *, force: bool = False) -> Path:
    """PTR PDF를 받아 캐시에 저장하고 경로를 반환한다.

    캐시에 이미 있으면 재다운로드하지 않는다(force=True면 강제).
    """
    path = _cache_path(year, doc_id)
    if path.exists() and path.stat().st_size > 0 and not force:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    url = PTR_PDF_URL.format(year=year, doc_id=doc_id)
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=60).read()
    path.write_bytes(data)
    time.sleep(REQUEST_DELAY_SEC)  # 서버 매너
    return path


if __name__ == "__main__":
    import sys

    from fetch_index import fetch_ptr_filings

    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    filings = fetch_ptr_filings(yr)[:3]
    for f in filings:
        p = fetch_pdf(yr, f.doc_id)
        print(f"{f.doc_id}: {p} ({p.stat().st_size:,} bytes)")
