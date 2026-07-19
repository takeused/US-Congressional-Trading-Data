# 파싱·인리치된 JSON을 읽어 자립형 HTML 대시보드를 생성하는 모듈
import json
import sys
from collections import defaultdict
from pathlib import Path

from config import DATA_DIR, ROOT

MIN_N = 5  # 소표본 기준 — n<5는 상위 랭킹 제외 (가이드 §7)


def _load(year: int) -> list[dict]:
    return json.load(open(DATA_DIR / f"ptr_{year}.json", encoding="utf-8"))


def _aggregate(recs: list[dict]) -> dict:
    """대시보드용 집계: 요약·의원별·섹터별·티커별·최근거래."""
    stock = [r for r in recs if r["asset_type"] == "stock" and r["ticker"]]
    enriched = [r for r in stock if r.get("return_pct") is not None]

    # 의원별 수익률 (표본수 n 병기)
    by_member = defaultdict(list)
    for r in enriched:
        by_member[r["filer"]].append(r["return_pct"])
    members = [
        {
            "name": m,
            "n": len(v),
            "avg_return": round(sum(v) / len(v), 2),
            "win_rate": round(100 * sum(1 for x in v if x > 0) / len(v), 1),
        }
        for m, v in by_member.items()
    ]
    # n>=MIN_N만 랭킹, 평균수익률 내림차순
    ranked_members = sorted(
        [m for m in members if m["n"] >= MIN_N],
        key=lambda x: x["avg_return"],
        reverse=True,
    )

    # 섹터별 수급 (매수/매도 건수)
    by_sector = defaultdict(lambda: {"buy": 0, "sell": 0})
    for r in stock:
        sec = r.get("sector") or "Unknown"
        if r["type"] in ("buy", "sell"):
            by_sector[sec][r["type"]] += 1
    sectors = sorted(
        ({"sector": s, **v, "total": v["buy"] + v["sell"]} for s, v in by_sector.items()),
        key=lambda x: x["total"],
        reverse=True,
    )

    # 인기 티커 (거래 건수)
    by_ticker = defaultdict(lambda: {"buy": 0, "sell": 0})
    for r in stock:
        if r["type"] in ("buy", "sell"):
            by_ticker[r["ticker"]][r["type"]] += 1
    tickers = sorted(
        ({"ticker": t, **v, "total": v["buy"] + v["sell"]} for t, v in by_ticker.items()),
        key=lambda x: x["total"],
        reverse=True,
    )[:20]

    return {
        "summary": {
            "transactions": len(recs),
            "stock_txns": len(stock),
            "enriched": len(enriched),
            "members": len(by_member),
            "ocr_txns": sum(1 for r in recs if r.get("source") == "ocr"),
            "ocr_buy": sum(1 for r in recs if r.get("source") == "ocr" and r["type"] == "buy"),
            "ocr_sell": sum(1 for r in recs if r.get("source") == "ocr" and r["type"] == "sell"),
            "avg_return": round(sum(r["return_pct"] for r in enriched) / len(enriched), 2)
            if enriched else None,
        },
        "members": ranked_members,
        "sectors": sectors,
        "tickers": tickers,
    }


def _html(year: int, agg: dict) -> str:
    """집계 결과를 자립형 HTML로 렌더 (데이터 임베드, 외부 의존 없음)."""
    data_json = json.dumps(agg, ensure_ascii=False)
    s = agg["summary"]
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>미 의회 매매 데이터 · {year}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
         margin: 0; padding: 24px; line-height: 1.5;
         background: #0f1115; color: #e6e8eb; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #9aa4af; font-size: 13px; margin-bottom: 20px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
           gap: 12px; margin-bottom: 24px; }}
  .card {{ background: #1a1d24; border: 1px solid #262b34; border-radius: 10px; padding: 14px; }}
  .card .v {{ font-size: 26px; font-weight: 700; }}
  .card .l {{ color: #9aa4af; font-size: 12px; }}
  section {{ background: #1a1d24; border: 1px solid #262b34; border-radius: 10px;
            padding: 16px; margin-bottom: 20px; overflow-x: auto; }}
  section h2 {{ font-size: 15px; margin: 0 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: right; padding: 7px 10px; border-bottom: 1px solid #262b34; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: #9aa4af; font-weight: 600; }}
  .pos {{ color: #4ade80; }}
  .neg {{ color: #f87171; }}
  .bar {{ display: inline-block; height: 8px; border-radius: 4px; vertical-align: middle; }}
  .buy {{ background: #4ade80; }} .sell {{ background: #f87171; }}
  .disc {{ color: #9aa4af; font-size: 12px; border-top: 1px solid #262b34;
          padding-top: 14px; margin-top: 8px; }}
  .n {{ color: #9aa4af; font-size: 11px; }}
</style>
</head>
<body>
<h1>🏛️ 미 의회 매매 데이터 · {year}</h1>
<div class="sub">미국 하원 재무공시(PTR) · STOCK Act 기반 공개 데이터 · 정보 제공용 (투자 권유 아님)</div>

<div class="cards">
  <div class="card"><div class="v">{s['transactions']:,}</div><div class="l">전체 거래</div></div>
  <div class="card"><div class="v">{s['stock_txns']:,}</div><div class="l">주식 거래</div></div>
  <div class="card"><div class="v">{s['members']}</div><div class="l">의원 수</div></div>
  <div class="card"><div class="v">{s['enriched']:,}</div><div class="l">수익률 계산</div></div>
  <div class="card"><div class="v">{'-' if s['avg_return'] is None else f"{s['avg_return']}%"}</div><div class="l">평균 수익률</div></div>
  <div class="card"><div class="v">{s['ocr_txns']:,}</div><div class="l">OCR 복원 (매수 {s['ocr_buy']}·매도 {s['ocr_sell']})</div></div>
</div>

<section>
  <h2>📈 의원별 성과 <span class="n">(공시일 종가 진입 → 현재가 · n≥{MIN_N}만 표시)</span></h2>
  <table id="members"><thead><tr>
    <th>의원</th><th>표본수 n</th><th>평균 수익률</th><th>승률</th></tr></thead><tbody></tbody></table>
</section>

<section>
  <h2>🧭 섹터별 수급 <span class="n">(매수/매도 건수)</span></h2>
  <table id="sectors"><thead><tr>
    <th>섹터</th><th>매수</th><th>매도</th><th>합계</th><th></th></tr></thead><tbody></tbody></table>
</section>

<section>
  <h2>🔥 인기 종목 Top 20 <span class="n">(거래 건수)</span></h2>
  <table id="tickers"><thead><tr>
    <th>티커</th><th>매수</th><th>매도</th><th>합계</th></tr></thead><tbody></tbody></table>
</section>

<div class="disc">
  ⚠️ 표본수(n)가 작을수록 신뢰도가 낮습니다. n&lt;{MIN_N} 의원은 랭킹에서 제외했습니다.
  과거 성과는 미래 수익을 보장하지 않으며, 의원 매매 추종의 실증 알파는 대체로 약하고
  표본편향이 큽니다. 본 대시보드는 <b>투명성·참고용</b> 도구이지 자동매매 신호가 아닙니다.
</div>

<script>
const DATA = {data_json};
const fmtPct = v => (v>0?'+':'') + v + '%';
const cls = v => v>0?'pos':(v<0?'neg':'');

const mb = document.querySelector('#members tbody');
DATA.members.forEach(m => {{
  mb.insertAdjacentHTML('beforeend',
    `<tr><td>${{m.name}}</td><td>${{m.n}}</td>`+
    `<td class="${{cls(m.avg_return)}}">${{fmtPct(m.avg_return)}}</td>`+
    `<td>${{m.win_rate}}%</td></tr>`);
}});
if (!DATA.members.length) mb.innerHTML = '<tr><td colspan="4">n≥5 의원 없음</td></tr>';

const maxSec = Math.max(1, ...DATA.sectors.map(x=>x.total));
const sb = document.querySelector('#sectors tbody');
DATA.sectors.forEach(x => {{
  const w = Math.round(120*x.total/maxSec);
  sb.insertAdjacentHTML('beforeend',
    `<tr><td>${{x.sector}}</td><td>${{x.buy}}</td><td>${{x.sell}}</td>`+
    `<td>${{x.total}}</td><td style="text-align:left">`+
    `<span class="bar buy" style="width:${{Math.round(w*x.buy/x.total)}}px"></span>`+
    `<span class="bar sell" style="width:${{Math.round(w*x.sell/x.total)}}px"></span></td></tr>`);
}});

const tb = document.querySelector('#tickers tbody');
DATA.tickers.forEach(x => {{
  tb.insertAdjacentHTML('beforeend',
    `<tr><td>${{x.ticker}}</td><td>${{x.buy}}</td><td>${{x.sell}}</td><td>${{x.total}}</td></tr>`);
}});
</script>
</body>
</html>"""


def build(year: int) -> Path:
    recs = _load(year)
    agg = _aggregate(recs)
    out = ROOT / "dashboard" / f"index_{year}.html"
    out.write_text(_html(year, agg), encoding="utf-8")
    print(f"대시보드 생성: {out}")
    return out


if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    build(yr)
