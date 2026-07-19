# 연도별 공시 인덱스 ZIP을 받아 PTR(FilingType=='P') 목록을 추출하는 모듈
import io
import zipfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

from config import UA, INDEX_ZIP_URL


@dataclass
class Filing:
    """PTR 공시 한 건의 인덱스 메타데이터."""
    doc_id: str
    filing_date: str
    last: str
    first: str
    state_dst: str
    year: int


def _download_index_xml(year: int) -> bytes:
    """{year}FD.zip을 받아 내부 {year}FD.xml 바이트를 반환한다."""
    url = INDEX_ZIP_URL.format(year=year)
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=60).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    return zf.read(f"{year}FD.xml")


def fetch_ptr_filings(year: int) -> list[Filing]:
    """해당 연도 인덱스에서 FilingType=='P'(PTR) 공시만 반환한다."""
    xml = _download_index_xml(year)
    root = ET.fromstring(xml)
    filings: list[Filing] = []
    for m in root.findall("Member"):
        if (m.findtext("FilingType") or "").strip() != "P":
            continue
        doc_id = (m.findtext("DocID") or "").strip()
        if not doc_id:
            continue
        filings.append(
            Filing(
                doc_id=doc_id,
                filing_date=(m.findtext("FilingDate") or "").strip(),
                last=(m.findtext("Last") or "").strip(),
                first=(m.findtext("First") or "").strip(),
                state_dst=(m.findtext("StateDst") or "").strip(),
                year=year,
            )
        )
    return filings


if __name__ == "__main__":
    import sys

    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    fs = fetch_ptr_filings(yr)
    print(f"{yr} PTR 공시: {len(fs)}건")
    for f in fs[:5]:
        print(" ", asdict(f))
