# 파이프라인 전역 상수와 경로를 정의하는 설정 모듈
from pathlib import Path

# 프로젝트 루트 (src/의 부모)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
PDF_CACHE_DIR = CACHE_DIR / "pdf"

# 봇 차단 회피용 정상 브라우저 UA (가이드 §1)
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# 하원 사무처 공식 배포 URL 템플릿 (가이드 §1, §2)
INDEX_ZIP_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"

# 요청 간 대기 (서버 매너, 가이드 §2)
REQUEST_DELAY_SEC = 0.15

# 자산유형 코드 (가이드 §4 + 실제 PTR에서 관측된 추가 코드)
ASSET_TYPE = {
    "ST": "stock",           # 주식
    "OP": "option",          # 옵션
    "MF": "mutual_fund",     # 뮤추얼펀드
    "GS": "govt_security",   # 국채·정부기관채
    "OT": "other",           # 기타 (ETF 등)
    "CS": "corporate_bond",  # 회사채
    "HN": "hedge_fund",      # 헤지펀드
    "PE": "private_equity",  # 사모펀드
    "EF": "exchange_fund",   # 익스체인지 펀드
    "RP": "real_property",   # 부동산
    "CT": "corporate_bond",  # 회사채(대체 표기)
}

# 거래유형 코드
TXN_KIND = {"S": "sell", "P": "buy", "E": "exchange"}


def ensure_dirs():
    """데이터·캐시 디렉토리를 생성한다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
