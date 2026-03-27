#!/usr/bin/env python3
"""
OMRON News Intelligence
- 한국어 6개 카테고리 수집 후 일본어 번역 방식
- API 호출 절반 절약, 안정성 향상
"""

import json, os, sys, time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    sys.exit(1)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"

CATEGORIES = [
    {"id": "omron",      "label_ko": "OMRON 소식",    "label_ja": "オムロン情報",   "icon": "🏢", "color": "#0066CC",
     "queries": ["Omron Corporation news 2026", "오므론 전자부품 최신 뉴스 2026"],
     "desc_ko": "오므론 본사 및 글로벌 소식", "desc_ja": "オムロン本社・グローバルニュース"},
    {"id": "hfe",        "label_ko": "HFE",            "label_ja": "HFE",            "icon": "📡", "color": "#7C3AED",
     "queries": ["semiconductor inspection equipment news 2026", "카메라모듈 디스플레이 검사장비 뉴스 2026", "반도체 검사 장비 업계 동향 2026"],
     "desc_ko": "고주파장비 · 모바일검사 · 반도체장비", "desc_ja": "高周波装置・モバイル検査・半導体装置"},
    {"id": "dce",        "label_ko": "DCE",            "label_ja": "DCE",            "icon": "⚡", "color": "#059669",
     "queries": ["LG에너지솔루션 SK온 삼성SDI 배터리 뉴스 2026", "ESS 에너지저장 데이터센터 전력 뉴스 2026", "DC power equipment high power industry 2026"],
     "desc_ko": "DC파워 · 배터리 · ESS · 데이터센터", "desc_ja": "DCパワー・バッテリー・ESS・データセンター"},
    {"id": "appliance",  "label_ko": "가전업계",       "label_ja": "家電業界",       "icon": "🏠", "color": "#DC2626",
     "queries": ["LG전자 삼성전자 가전제품 신제품 뉴스 2026", "Korea home appliance industry news 2026"],
     "desc_ko": "LG · 삼성 가전제품 동향", "desc_ja": "LG・サムスン 家電製品動向"},
    {"id": "casino",     "label_ko": "카지노 머신",    "label_ja": "カジノ機器",     "icon": "🎰", "color": "#D97706",
     "queries": ["casino slot machine gaming industry news 2026", "gaming machine electronic component Asia 2026"],
     "desc_ko": "카지노 머신 · 게이밍 장비", "desc_ja": "カジノ機器・ゲーミング装置"},
    {"id": "electronics","label_ko": "전자산업 동향",  "label_ja": "電子産業動向",   "icon": "🔌", "color": "#0891B2",
     "queries": ["한국 전자산업 동향 뉴스 2026", "electronic component relay switch connector Korea 2026"],
     "desc_ko": "릴레이 · 스위치 · 커넥터 범용부품 산업", "desc_ja": "リレー・スイッチ・コネクタ 汎用部品産業"},
]

SYS_KO = """당신은 전자부품 산업 전문 뉴스 분석가입니다. 오므론전자부품 기술영업팀을 위해 주간 뉴스를 분석합니다.
검색 결과를 바탕으로 다음 형식의 JSON만 반환하세요:
{"articles":[{"title":"기사제목(반드시한국어)","summary":"요약(반드시한국어)","insight":"인사이트(반드시한국어)","source":"출처명","url":"URL","date":"YYYY-MM-DD","importance":"high|medium|low"}]}
규칙:
- JSON만 출력(마크다운 코드블록 없이)
- 최대 5개 기사
- title, summary, insight 모두 반드시 한국어로 작성 (영어 제목을 한국어로 번역해서 쓸 것)
- 이번 주(최근 7일) 신규 기사 최우선, 없으면 최근 1개월 내 주요 뉴스"""

SYS_TRANSLATE = """You are a professional Japanese translator.
Translate the following JSON from Korean to Japanese.
- Translate ONLY the values of: title, summary, insight
- Do NOT change: source, url, date, importance
- Return ONLY valid JSON in exact same structure
- No markdown, no explanation, no extra text"""


def _parse(text, label):
    if not text.strip():
        return []
    c = text.replace("```json","").replace("```","").strip()
    s = c.find("{")
    if s == -1:
        print(f"  ⚠ {label}: JSON 없음")
        return []
    d = 0
    for i in range(s, len(c)):
        if c[i] == "{": d += 1
        elif c[i] == "}":
            d -= 1
            if d == 0:
                try:
                    arts = json.loads(c[s:i+1]).get("articles", [])
                    print(f"  ✅ {len(arts)}개")
                    return arts
                except:
                    return []
    return []


def fetch_ko(cat, retries=2):
    if not ANTHROPIC_API_KEY:
        return []
    hdrs = {"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"}
    q = ", ".join(cat["queries"])
    for attempt in range(retries+1):
        if attempt:
            w = 15*attempt
            print(f"  ↻ 재시도 {attempt} ({w}초)...")
            time.sleep(w)
        try:
            msgs = [{"role":"user","content":f"이번 주 신규 발표 최우선, 없으면 최근 1개월 주요 뉴스: {q}\n카테고리: {cat['label_ko']} ({cat['desc_ko']})"}]
            for _ in range(10):
                r = requests.post(API_URL, headers=hdrs, json={"model":MODEL,"max_tokens":4000,"system":SYS_KO,"tools":[{"type":"web_search_20250305","name":"web_search"}],"messages":msgs}, timeout=120)
                r.raise_for_status()
                d = r.json()
                sr = d.get("stop_reason","")
                cb = d.get("content",[])
                msgs.append({"role":"assistant","content":cb})
                tp = [b["text"] for b in cb if b.get("type")=="text"]
                if sr == "end_turn":
                    return _parse(" ".join(tp), cat["label_ko"])
                elif sr == "tool_use":
                    tr = [{"type":"tool_result","tool_use_id":b["id"],"content":"OK"} for b in cb if b.get("type")=="tool_use"]
                    if tr:
                        msgs.append({"role":"user","content":tr})
                    else:
                        return _parse(" ".join(tp), cat["label_ko"])
                else:
                    t = " ".join(tp)
                    if t: return _parse(t, cat["label_ko"])
                    break
        except requests.exceptions.Timeout:
            print(f"  ⏱ 타임아웃")
        except requests.exceptions.HTTPError as e:
            s = e.response.status_code if e.response else "?"
            print(f"  ❌ HTTP {s}")
            if s == 429:
                time.sleep(30)
        except Exception as e:
            print(f"  ❌ {e}")
    return []


def translate_ja(articles, label):
    """기사 목록을 일본어로 번역. 실패시 개별 번역 시도."""
    if not articles:
        return []
    hdrs = {"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"}
    
    def _translate_one(art):
        payload = json.dumps({
            "title": art.get("title",""),
            "summary": art.get("summary",""),
            "insight": art.get("insight","")
        }, ensure_ascii=False)
        try:
            r = requests.post(API_URL, headers=hdrs, json={
                "model": MODEL,
                "max_tokens": 1500,
                "system": SYS_TRANSLATE,
                "messages": [{"role":"user","content": payload}]
            }, timeout=60)
            r.raise_for_status()
            t = " ".join(b["text"] for b in r.json().get("content",[]) if b.get("type")=="text")
            t = t.replace("```json","").replace("```","").strip()
            translated = json.loads(t)
            return {**art,
                "title": translated.get("title", art.get("title","")),
                "summary": translated.get("summary", art.get("summary","")),
                "insight": translated.get("insight", art.get("insight",""))}
        except Exception as e:
            print(f"    ⚠ 개별 번역 실패: {e}")
            return art
    
    results = []
    for i, art in enumerate(articles):
        print(f"    [{i+1}/{len(articles)}] 번역 중...")
        results.append(_translate_one(art))
        if i < len(articles)-1:
            time.sleep(1)
    print(f"  ✅ {len(results)}개 번역 완료")
    return results


def generate_html(all_news, update_time, lang="ko", other_lang_url=None):
    is_ja = lang == "ja"
    font_url = ("https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
                if is_ja else
                "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap")
    font_fam = "'Noto Sans JP',sans-serif" if is_ja else "'Noto Sans KR',sans-serif"
    lang_btn = f'<a href="{other_lang_url}" class="lang-btn">{"한국어" if is_ja else "日本語"}</a>' if other_lang_url else ""

    tabs, sections = [], []
    for idx, cat in enumerate(CATEGORIES):
        cid = cat["id"]
        arts = all_news.get(cid, [])
        lbl = cat["label_ja"] if is_ja else cat["label_ko"]
        dsc = cat["desc_ja"] if is_ja else cat["desc_ko"]
        first = idx == 0

        tabs.append(f"""<button class="tab {'active' if first else ''}" data-category="{cid}" onclick="showCategory('{cid}')" style="--cat-color:{cat['color']}">
            <span class="tab-icon">{cat['icon']}</span><span class="tab-label">{lbl}</span>
            {f'<span class="tab-badge" style="background:{cat["color"]}">{len(arts)}</span>' if arts else ''}
        </button>""")

        cards = []
        if arts:
            for a in arts:
                imp = a.get("importance","medium")
                ic = {"high":"#DC2626","medium":"#D97706","low":"#6B7280"}.get(imp,"#6B7280")
                il = {"high":"高" if is_ja else "높음","medium":"中" if is_ja else "보통","low":"低" if is_ja else "낮음"}.get(imp,"中" if is_ja else "보통")
                ip = "重要度:" if is_ja else "중요도:"
                ins_lbl = "営業インサイト:" if is_ja else "영업 인사이트:"
                rm = "記事を読む →" if is_ja else "원문 보기 →"
                ns = "情報源確認中" if is_ja else "출처 확인 중"
                url_h = f'<a href="{a["url"]}" target="_blank" rel="noopener noreferrer" class="source-link" style="color:{cat["color"]}">{rm}</a>' if a.get("url") else ""
                cards.append(f"""<article class="card" style="border-left-color:{ic}">
                    <div class="card-top"><span class="importance" style="background:{ic}18;color:{ic}">{ip} {il}</span><span class="date">{a.get('date','')}</span></div>
                    <h3 class="card-title">{a.get('title','')}</h3>
                    <p class="card-summary">{a.get('summary','')}</p>
                    <div class="insight-box"><span class="insight-icon">💡</span><p class="insight-text"><strong>{ins_lbl}</strong> {a.get('insight','')}</p></div>
                    <div class="card-footer"><span class="source">📌 {a.get('source',ns)}</span>{url_h}</div>
                </article>""")
            arts_html = "\n".join(cards)
        else:
            et = "ニュースが収集されていません" if is_ja else "수집된 뉴스가 없습니다"
            es = "次回の更新をお待ちください" if is_ja else "다음 업데이트를 기다려주세요"
            arts_html = f'<div class="empty"><div class="empty-icon">{cat["icon"]}</div><p class="empty-title">{et}</p><p class="empty-sub">{es}</p></div>'

        cl = f"{len(arts)}件" if is_ja else f"{len(arts)}개 기사"
        sections.append(f"""<section class="category-section {'active' if first else ''}" id="section-{cid}">
            <div class="cat-header"><div><div class="cat-title-row"><span class="cat-icon">{cat['icon']}</span><h2 class="cat-title" style="color:{cat['color']}">{lbl}</h2></div><p class="cat-desc">{dsc}</p></div><span class="article-count">{cl}</span></div>
            <div class="articles">{arts_html}</div>
        </section>""")

    total = sum(len(all_news.get(c["id"],[]))for c in CATEGORIES)
    high  = sum(1 for c in CATEGORIES for a in all_news.get(c["id"],[]) if a.get("importance")=="high")
    tabs_h, secs_h = "\n".join(tabs), "\n".join(sections)

    if is_ja:
        sub="オムロン電子部品 社員の皆様のための産業ニュースダッシュボード"; al="本日の記事"; hl="重要度: 高"; cl2="カテゴリ数"; ul="週間更新:"; ft="Powered by Claude AI · オムロン電子部品 Choi Hongsun · 毎週月曜日 午前6時自動更新"
    else:
        sub="오므론전자부품 사우분들을 위한 산업 뉴스 대시보드"; al="오늘의 기사"; hl="높은 중요도"; cl2="분석 카테고리"; ul="주간 업데이트:"; ft="Powered by Claude AI · 오므론전자부품 최홍선 · 매주 월요일 오전 6시 자동 업데이트"

    return f"""<!DOCTYPE html>
<html lang="{'ja' if is_ja else 'ko'}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OMRON News Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{font_url}" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#F5F6FA;--surface:#fff;--text:#1A1A2E;--text-secondary:#6B7280;--text-muted:#9CA3AF;--border:#E5E7EB;--header-bg:linear-gradient(135deg,#0A0F1E 0%,#162040 50%,#1A2744 100%)}}
body{{font-family:{font_fam};background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}}
header{{background:var(--header-bg);padding:28px 24px 20px;position:relative;overflow:hidden}}
header::before{{content:'';position:absolute;top:-50%;right:-10%;width:400px;height:400px;background:radial-gradient(circle,rgba(0,102,204,.12) 0%,transparent 70%);border-radius:50%}}
.header-inner{{max-width:1100px;margin:0 auto;position:relative;z-index:1}}
.logo-row{{display:flex;align-items:center;gap:14px;margin-bottom:16px}}
.logo-mark{{width:46px;height:46px;border-radius:12px;background:linear-gradient(135deg,#0066CC,#00AAFF);display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:17px;color:#fff;letter-spacing:-1px;flex-shrink:0}}
.logo-text{{flex:1}}.site-title{{font-size:22px;font-weight:800;color:#fff;letter-spacing:-.5px}}
.site-subtitle{{font-size:12px;color:rgba(255,255,255,.55);font-weight:300;margin-top:2px}}
.lang-btn{{display:inline-block;padding:5px 14px;border:1px solid rgba(255,255,255,.3);border-radius:20px;color:rgba(255,255,255,.8);font-size:12px;font-weight:500;text-decoration:none;transition:all .2s;white-space:nowrap}}
.lang-btn:hover{{background:rgba(255,255,255,.15);color:#fff}}
.stats-row{{display:flex;gap:24px;flex-wrap:wrap;align-items:center}}
.stat{{display:flex;align-items:center;gap:8px}}
.stat-value{{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:600;color:#fff}}
.stat-label{{font-size:11px;color:rgba(255,255,255,.5);line-height:1.3}}
.update-time{{margin-top:12px;font-size:11px;color:rgba(255,255,255,.35);font-family:'JetBrains Mono',monospace}}
nav{{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.tab-scroll{{max-width:1100px;margin:0 auto;display:flex;gap:4px;padding:10px 24px;overflow-x:auto;-webkit-overflow-scrolling:touch}}
.tab-scroll::-webkit-scrollbar{{height:0}}
.tab{{display:flex;align-items:center;gap:7px;padding:9px 16px;border-radius:8px;border:1.5px solid transparent;background:transparent;color:var(--text-secondary);font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap;font-family:inherit;transition:all .2s}}
.tab:hover{{background:#F3F4F6}}
.tab.active{{background:color-mix(in srgb,var(--cat-color) 8%,transparent);border-color:var(--cat-color);color:var(--cat-color);font-weight:600}}
.tab-icon{{font-size:17px}}.tab-badge{{font-size:10px;font-weight:700;color:#fff;border-radius:10px;padding:1px 7px;min-width:18px;text-align:center}}
main{{max-width:1100px;margin:0 auto;padding:24px}}
.category-section{{display:none;animation:fadeIn .3s ease}}.category-section.active{{display:block}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.cat-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;flex-wrap:wrap;gap:12px}}
.cat-title-row{{display:flex;align-items:center;gap:10px}}.cat-icon{{font-size:28px}}
.cat-title{{font-size:22px;font-weight:800;letter-spacing:-.5px}}.cat-desc{{font-size:13px;color:var(--text-secondary);margin-top:3px}}
.article-count{{font-size:12px;color:var(--text-muted);background:#F3F4F6;padding:4px 12px;border-radius:20px;font-weight:500}}
.articles{{display:flex;flex-direction:column;gap:14px}}
.card{{background:var(--surface);border-radius:12px;padding:20px 24px;border-left:4px solid;box-shadow:0 1px 4px rgba(0,0,0,.04);transition:all .2s}}
.card:hover{{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.07)}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.importance{{font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px}}
.date{{font-size:12px;color:var(--text-muted);font-family:'JetBrains Mono',monospace}}
.card-title{{font-size:16px;font-weight:700;color:#111827;line-height:1.45;margin-bottom:10px;letter-spacing:-.3px}}
.card-summary{{font-size:13.5px;color:#4B5563;line-height:1.75;margin-bottom:14px}}
.insight-box{{display:flex;gap:8px;background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:12px 14px;margin-bottom:14px}}
.insight-icon{{font-size:16px;flex-shrink:0;margin-top:1px}}.insight-text{{font-size:12.5px;color:#92400E;line-height:1.65}}
.card-footer{{display:flex;justify-content:space-between;align-items:center;padding-top:10px;border-top:1px solid #F3F4F6}}
.source{{font-size:12px;color:var(--text-muted)}}.source-link{{font-size:12px;font-weight:600;text-decoration:none;transition:opacity .2s}}.source-link:hover{{opacity:.7}}
.empty{{text-align:center;padding:60px 20px}}.empty-icon{{font-size:48px;opacity:.3;margin-bottom:12px}}
.empty-title{{font-size:15px;font-weight:600;color:#374151}}.empty-sub{{font-size:13px;color:var(--text-muted);margin-top:4px}}
footer{{text-align:center;padding:28px 24px;font-size:11px;color:var(--text-muted);border-top:1px solid var(--border);margin-top:48px}}
@media(max-width:640px){{header{{padding:20px 16px}}.site-title{{font-size:18px}}main{{padding:16px}}.card{{padding:16px}}.cat-title{{font-size:18px}}.tab{{padding:7px 12px;font-size:12px}}}}
</style></head><body>
<header><div class="header-inner">
    <div class="logo-row"><div class="logo-mark">ON</div><div class="logo-text"><h1 class="site-title">OMRON News Intelligence</h1><p class="site-subtitle">{sub}</p></div>{lang_btn}</div>
    <div class="stats-row"><div class="stat"><span class="stat-value">{total}</span><span class="stat-label">{al}</span></div><div class="stat"><span class="stat-value">{high}</span><span class="stat-label">{hl}</span></div><div class="stat"><span class="stat-value">{len(CATEGORIES)}</span><span class="stat-label">{cl2}</span></div></div>
    <p class="update-time">{ul} {update_time}</p>
</div></header>
<nav><div class="tab-scroll">{tabs_h}</div></nav>
<main>{secs_h}</main>
<footer>{ft}</footer>
<script>
function showCategory(id){{
    document.querySelectorAll('.category-section').forEach(s=>s.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.getElementById('section-'+id).classList.add('active');
    document.querySelector('[data-category="'+id+'"]').classList.add('active');
}}
</script></body></html>"""


def main():
    print("="*55)
    print("OMRON News Intelligence - 시작")
    print("="*55)
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    t_ko = now.strftime("%Y년 %m월 %d일 %H:%M KST")
    t_ja = now.strftime("%Y年%m月%d日 %H:%M KST")
    if not ANTHROPIC_API_KEY:
        print("API 키 없음!"); sys.exit(1)

    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(out, exist_ok=True)

    print("\n[ 1단계: 한국어 수집 ]")
    news_ko = {}
    for i, cat in enumerate(CATEGORIES):
        print(f"\n[{i+1}/6] {cat['icon']} {cat['label_ko']}...")
        news_ko[cat["id"]] = fetch_ko(cat)
        if i < len(CATEGORIES)-1: time.sleep(8)

    print("\n\n[ 2단계: 일본어 번역 ]")
    news_ja = {}
    for i, cat in enumerate(CATEGORIES):
        arts = news_ko.get(cat["id"], [])
        if arts:
            print(f"\n[{i+1}/6] {cat['icon']} {cat['label_ja']} 번역...")
            news_ja[cat["id"]] = translate_ja(arts, cat["label_ja"])
            time.sleep(2)
        else:
            print(f"\n[{i+1}/6] {cat['icon']} {cat['label_ja']} - 기사 없음")
            news_ja[cat["id"]] = []

    print("\n\n[ 3단계: HTML 생성 ]")
    ko_p = os.path.join(out, "index.html")
    ja_p = os.path.join(out, "index_ja.html")
    with open(ko_p, "w", encoding="utf-8") as f:
        f.write(generate_html(news_ko, t_ko, lang="ko", other_lang_url="index_ja.html"))
    with open(ja_p, "w", encoding="utf-8") as f:
        f.write(generate_html(news_ja, t_ja, lang="ja", other_lang_url="index.html"))

    tk = sum(len(v) for v in news_ko.values())
    tj = sum(len(v) for v in news_ja.values())
    print(f"\n완료! 한국어 {tk}개 / 일본어 {tj}개")
    print("="*55)

if __name__ == "__main__":
    main()
