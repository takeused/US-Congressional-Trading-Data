<!-- 미 의회 PTR 매매 데이터 파이프라인 작업 체크리스트 -->
# 체크리스트 — 미 의회 매매 데이터 파이프라인

## 프로젝트 셋업
- [x] 디렉토리 구조 생성 (`src/`, `data/`, `cache/pdf/`, `dashboard/`)
- [x] `requirements.txt` 작성 (yfinance 등)
- [x] `README.md` — 실행법 요약

## ① 인덱스 — 연도별 공시 목록 (`src/fetch_index.py`)
- [x] `{YEAR}FD.zip` 다운로드 (정상 UA 헤더)
- [x] ZIP 내부 `{YEAR}FD.xml` 추출·파싱
- [x] `FilingType == 'P'` (PTR) 필터
- [x] 필드 추출: DocID, FilingDate, Last, First, StateDst
- [x] 검증: PTR 건수 출력, 샘플 5건 확인

## ② PDF 다운로드 (`src/fetch_pdf.py`)
- [x] `ptr-pdfs/{YEAR}/{DocID}.pdf` URL 조립·다운로드
- [x] 로컬 캐시 (`cache/pdf/{YEAR}/{DocID}.pdf`) — 있으면 스킵
- [x] 요청 간 `time.sleep(0.15)`
- [x] 검증: 캐시 재실행 시 재다운로드 안 함

## ③ 텍스트 추출 (`src/extract.py`)
- [x] `pdftotext -layout` 호출 (timeout=20)
- [x] 빈 결과(<50자) → 스캔 PDF 플래그 반환
- [x] 검증: 정상/스캔 PDF 구분

## ④ 정규식 파싱 (`src/parse.py`)
- [x] TXN_RE (유형·거래일·공시일·금액구간)
- [x] TICKER_RE (티커·자산유형코드)
- [x] 엣지케이스 1: 금액구간 줄바꿈 결합
- [x] 엣지케이스 2: 스캔 PDF 스킵/표시
- [x] 엣지케이스 3: 티커 없음 → null
- [x] 엣지케이스 4: 거래일 > 공시일 행 제외
- [x] 엣지케이스 5: 이름 정규화 (first+last, last fallback)
- [x] JSON 스키마: {filer, ticker, type, amount, transaction_date, notification_date, ...}
- [x] 검증: 파싱 건수·티커 null 비율(~35%) 확인

## ⑤ 인리치 (`src/enrich.py`)
- [x] yfinance 설치·연동
- [x] 가격 이력 (`history(period="2y")`)
- [x] 섹터·기업설명 (`.info`)
- [x] 공시일 종가 진입 → 현재가 수익률 계산 (표본수 n 병기)
- [x] 의원 프로필 (`congress-legislators`)
- [x] 검증: 수익률·섹터 붙은 레코드 샘플 확인

## 파이프라인 통합 (`src/pipeline.py`)
- [x] `--year` 인자 파싱 (argparse)
- [x] ①~⑤ 순차 실행 → `data/ptr_{YEAR}.json`
- [x] 진행 로그·에러 집계

## 대시보드 (`dashboard/`)
- [x] JSON → HTML 대시보드 (수익률·수급·테마·의원 프로필)
- [x] 통계 정직성: 표본수 n 병기, 소표본(n<5) 상위 제외, 고지 문구
- [x] 검증: 브라우저에서 렌더 확인

## 마무리
- [x] 전체 파이프라인 E2E 실행 (실제 연도)
- [x] 산출물 검수
