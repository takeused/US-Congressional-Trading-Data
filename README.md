# 미 의회 매매 데이터 파이프라인

미국 하원 사무처 재무공시(PTR)를 공식 배포 파일에서 다운로드·파싱해 구조화 JSON을 만들고, 시세 인리치·대시보드까지 생성하는 파이프라인. 근거: `미 의회 매매 데이터 — 공식 소스 파싱 가이드.md`.

## 파이프라인

```
① fetch_index  연도별 {YEAR}FD.zip → XML → FilingType=='P'(PTR) 필터
② fetch_pdf    DocID로 PTR PDF 다운로드 + 로컬 캐시 (sleep 0.15)
③ extract      pdftotext -layout, 스캔 PDF 감지
④ parse        정규식 파싱 (거래유형·날짜·금액·티커) + 엣지케이스
   └ ocr        스캔(구형 종이양식) → PyMuPDF 렌더 + RapidOCR → 스캔 전용 파서
⑤ enrich       yfinance 시세·섹터·수익률 (선택)
→ dashboard    자립형 HTML 대시보드
```

## 요구사항

- Python 3.10+
- `pdftotext` (poppler) — PATH에 있어야 함
- `pip install -r requirements.txt` (yfinance, 인리치용)

## 실행

```bash
cd src

# 전체 파이프라인 (파싱만)
python pipeline.py --year 2026

# 인리치 포함 (yfinance 시세·수익률)
python pipeline.py --year 2026 --enrich

# 스캔(구형 양식) OCR 복원 포함 (느림)
python pipeline.py --year 2026 --ocr --enrich

# 테스트: 앞 30건만
python pipeline.py --year 2026 --limit 30

# 대시보드 생성
python dashboard.py 2026    # → dashboard/index_2026.html
```

단계별 단독 실행도 가능하다 (`python fetch_index.py 2026`, `python parse.py 2026 <DocID>` 등).

## 산출물

- `data/ptr_{YEAR}.json` — 거래 레코드 배열
  ```json
  {"filer","state_dst","doc_id","asset_name","ticker","asset_type","owner",
   "type","amount","transaction_date","notification_date","source",
   "sector","industry","entry_price","current_price","return_pct"}
  ```
  `source`: `text`(전자 PTR) / `ocr`(구형 스캔양식). OCR 행은 `type`·`amount`가
  체크박스라 복원 불가 → 빈 값. 수익률·섹터 통계에서 자동 제외됨.
- `cache/pdf/{YEAR}/{DocID}.pdf` — 다운로드 PDF 캐시 (재실행 시 재다운로드 방지)
- `dashboard/index_{YEAR}.html` — 대시보드 (데이터 임베드, 브라우저에서 바로 열기)

## 2026년 검증 결과

- 308 공시 → 2,552 거래
- 주식 1,250건 중 티커 추출 1,247건 (99.8%)
- 수익률 계산 1,221건
- 스캔 PDF 33건은 스킵 (OCR 미도입)

## 스캔 PDF OCR (구형 종이양식)

33개 스캔 PDF는 전자화 이전의 **종이 체크박스 양식**이다. `--ocr` 옵션으로:

- PyMuPDF로 페이지 렌더 → RapidOCR(ONNX, 오프라인)로 텍스트화 → 좌표 기반 행 복원
- 복원 필드: **자산명·티커(괄호형)·거래일·공시일·소유자** (`source=ocr`)
- 거래유형·금액은 체크박스 X 표시라 OCR로 신뢰 복원 불가 → 빈 값. 따라서
  수익률·섹터 통계에는 포함되지 않고 "거래 존재" 기록으로만 남는다.
- 티커는 정확도 위해 **괄호형만** 채택(트레일링 심볼은 Common→CMN 등 노이즈).

## 한계 / TODO

- **티커 없는 자산** — 국채·회사채·사모펀드·LP는 본래 티커가 없어 null (정상).
- **OCR 거래유형/금액** — 체크박스 좌표 분석은 미도입(취약). 필요 시 LLM 비전 검토.
- **인리치 속도** — yfinance `.info`가 티커마다 느림. 대량 재실행 시 배치 다운로드 최적화 여지.
- **통계 정직성** — 표본수 n 병기, n<5 랭킹 제외, 투자 권유 아님. 의원 매매 추종의 실증 알파는 약하고 표본편향이 큼.
