#!/usr/bin/env python3
"""OMRON News Intelligence - 한국어 수집 후 일본어 번역"""
import json, os, sys, time, re
from datetime import datetime, timezone, timedelta
try:
    import requests
except ImportError:
    sys.exit(1)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-haiku-4-5-20251001"

CATEGORIES = [
    {"id":"omron",      "ko":"OMRON 소식",   "ja":"オムロン情報",  "icon":"🏢","color":"#0066CC",
     "desc_ko":"오므론 본사 및 글로벌 소식",           "desc_ja":"オムロン本社・グローバルニュース",
     "queries":["Omron Corporation news 2026","오므론 전자부품 최신 뉴스 2026"]},
    {"id":"hfe",        "ko":"HFE",           "ja":"HFE",           "icon":"📡","color":"#7C3AED",
     "desc_ko":"고주파장비 · 모바일검사 · 반도체장비",  "desc_ja":"高周波装置・モバイル検査・半導体装置",
     "queries":["semiconductor inspection equipment news 2026","카메라모듈 디스플레이 검사장비 뉴스 2026","반도체 검사 장비 업계 동향 2026"]},
    {"id":"dce",        "ko":"DCE",           "ja":"DCE",           "icon":"⚡","color":"#059669",
     "desc_ko":"DC파워 · 배터리 · ESS · 데이터센터",  "desc_ja":"DCパワー・バッテリー・ESS・データセンター",
     "queries":["LG에너지솔루션 SK온 삼성SDI 배터리 뉴스 2026","ESS 에너지저장 데이터센터 전력 뉴스 2026","DC power equipment high power industry 2026"]},
    {"id":"appliance",  "ko":"가전업계",      "ja":"家電業界",      "icon":"🏠","color":"#DC2626",
     "desc_ko":"LG · 삼성 가전제품 동향",              "desc_ja":"LG・サムスン 家電製品動向",
     "queries":["LG전자 삼성전자 가전제품 신제품 뉴스 2026","Korea home appliance industry news 2026"]},
    {"id":"casino",     "ko":"카지노 머신",   "ja":"カジノ機器",    "icon":"🎰","color":"#D97706",
     "desc_ko":"카지노 머신 · 게이밍 장비",            "desc_ja":"カジノ機器・ゲーミング装置",
     "queries":["casino slot machine gaming industry news 2026","gaming machine electronic component Asia 2026"]},
    {"id":"electronics","ko":"전자산업 동향", "ja":"電子産業動向",  "icon":"🔌","color":"#0891B2",
     "desc_ko":"릴레이 · 스위치 · 커넥터 범용부품 산업","desc_ja":"リレー・スイッチ・コネクタ 汎用部品産業",
     "queries":["한국 전자산업 동향 뉴스 2026","electronic component relay switch connector Korea 2026"]},
]

SYS_KO = """당신은 전자부품 산업 뉴스 분석가입니다. 오므론전자부품 기술영업팀용 주간 뉴스를 분석합니다.
반드시 아래 JSON 형식만 출력하세요. 마크다운(```) 절대 금지.
{"articles":[{"title":"제목(한국어)","summary":"3~4문장 요약(한국어)","insight":"영업 인사이트(한국어)","source":"출처명","url":"URL","date":"YYYY-MM-DD","importance":"high|medium|low"}]}
규칙: 최대 5개, title/summary/insight 반드시 한국어, 영어 제목도 한국어로 번역, 이번 주 신규 기사 최우선"""

# 번역용: JSON 없이 텍스트로만 주고받기
SYS_JA = """You are a Japanese translator. Translate Korean text to Japanese.
Output format MUST be exactly:
TITLE: (translated title)
SUMMARY: (translated summary)
INSIGHT: (translated insight)
Only output these 3 lines. No extra text."""


def call_api(payload, timeout=120):
    """API 호출 공통 함수. 429시 자동 대기 후 재시도."""
    hdrs = {"Content-Type":"application/json","x-api-key":API_KEY,"anthropic-version":"2023-06-01"}
    for attempt in range(3):
        try:
            r = requests.post(API_URL, headers=hdrs, json=payload, timeout=timeout)
            if r.status_code == 429:
                wait = 45 * (attempt + 1)
                print(f"  ⏳ 속도 제한 — {wait}초 대기...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            print(f"  ⏱ 타임아웃 (시도 {attempt+1}/3)")
            time.sleep(10)
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP {e.response.status_code if e.response else '?'}")
            if attempt < 2:
                time.sleep(15)
        except Exception as e:
            print(f"  ❌ {e}")
            if attempt < 2:
                time.sleep(10)
    return None


def parse_articles(text, label=""):
    text = text.replace("```json","").replace("```","").strip()
    s = text.find("{")
    if s == -1:
        print(f"  ⚠ {label}: JSON 없음")
        return []
    depth = 0
    for i in range(s, len(text)):
        if text[i] == "{": depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    arts = json.loads(text[s:i+1]).get("articles",[])
                    print(f"  ✅ {len(arts)}개 수집")
                    return arts
                except:
                    return []
    return []


def fetch_ko(cat):
    """한국어 뉴스 수집 (웹 검색 멀티턴)"""
    if not API_KEY: return []
    q = ", ".join(cat["queries"])
    msgs = [{"role":"user","content":
             f"이번 주(최근 7일) 신규 발표·출시 최우선, 없으면 최근 1개월 주요 뉴스로 검색 분석:\n{q}\n카테고리: {cat['ko']} ({cat['desc_ko']})"}]

    for _ in range(12):
        data = call_api({"model":MODEL,"max_tokens":4000,"system":SYS_KO,
                         "tools":[{"type":"web_search_20250305","name":"web_search"}],
                         "messages":msgs})
        if not data:
            return []
        sr = data.get("stop_reason","")
        cb = data.get("content",[])
        msgs.append({"role":"assistant","content":cb})
        texts = [b["text"] for b in cb if b.get("type")=="text"]

        if sr == "end_turn":
            return parse_articles(" ".join(texts), cat["ko"])
        elif sr == "tool_use":
            tr = [{"type":"tool_result","tool_use_id":b["id"],"content":"OK"}
                  for b in cb if b.get("type")=="tool_use"]
            if tr:
                msgs.append({"role":"user","content":tr})
            else:
                return parse_articles(" ".join(texts), cat["ko"])
        else:
            t = " ".join(texts)
            if t: return parse_articles(t, cat["ko"])
            break
    return []


def translate_article(art):
    """기사 1개를 일본어로 번역. 텍스트 형식 사용(JSON 파싱 오류 방지)."""
    prompt = f"TITLE: {art.get('title','')}\nSUMMARY: {art.get('summary','')}\nINSIGHT: {art.get('insight','')}"
    data = call_api({"model":MODEL,"max_tokens":800,"system":SYS_JA,
                     "messages":[{"role":"user","content":prompt}]}, timeout=30)
    if not data:
        return art
    text = " ".join(b["text"] for b in data.get("content",[]) if b.get("type")=="text")

    # TITLE: / SUMMARY: / INSIGHT: 파싱
    title   = re.search(r"TITLE:\s*(.+?)(?:\n|$)", text)
    summary = re.search(r"SUMMARY:\s*(.+?)(?:\nINSIGHT:|$)", text, re.DOTALL)
    insight = re.search(r"INSIGHT:\s*(.+?)$", text, re.DOTALL)

    if title and summary and insight:
        return {**art,
            "title":   title.group(1).strip(),
            "summary": summary.group(1).strip(),
            "insight": insight.group(1).strip()}
    print(f"  ⚠ 번역 파싱 실패 — 원본 유지")
    return art


def translate_category(articles, label):
    results = []
    for i, art in enumerate(articles):
        print(f"    [{i+1}/{len(articles)}] 번역...")
        results.append(translate_article(art))
        if i < len(articles)-1:
            time.sleep(1)
    print(f"  ✅ {len(results)}개 완료")
    return results


def make_html(news, update_time, lang="ko", other_url=None):
    ja = (lang=="ja")
    font_url = ("https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
                if ja else
                "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap")
    font_fam = "'Noto Sans JP',sans-serif" if ja else "'Noto Sans KR',sans-serif"
    lang_btn = f'<a href="{other_url}" class="lang-btn">{"한국어" if ja else "日本語"}</a>' if other_url else ""
    sub  = "オムロン電子部品 社員の皆様のための産業ニュースダッシュボード" if ja else "오므론전자부품 사우분들을 위한 산업 뉴스 대시보드"
    al   = "本日の記事" if ja else "오늘의 기사"
    hl   = "重要度: 高" if ja else "높은 중요도"
    cl   = "カテゴリ数" if ja else "분석 카테고리"
    ul   = "週間更新:" if ja else "주간 업데이트:"
    ft   = "Powered by Claude AI · オムロン電子部品 Choi Hongsun · 毎週月曜日 午前6時自動更新" if ja else "Powered by Claude AI · 오므론전자부품 최홍선 · 매주 월요일 오전 6시 자동 업데이트"
    total = sum(len(news.get(c["id"],[])) for c in CATEGORIES)
    high  = sum(1 for c in CATEGORIES for a in news.get(c["id"],[]) if a.get("importance")=="high")

    tabs, secs = [], []
    for idx, cat in enumerate(CATEGORIES):
        cid  = cat["id"]; arts = news.get(cid,[]); first = (idx==0)
        lbl  = cat["ja"] if ja else cat["ko"]
        dsc  = cat["desc_ja"] if ja else cat["desc_ko"]
        imp_h= "高" if ja else "높음"; imp_m="中" if ja else "보통"; imp_l="低" if ja else "낮음"
        ip   = "重要度:" if ja else "중요도:"; il_lbl="営業インサイト:" if ja else "영업 인사이트:"
        rm   = "記事を読む →" if ja else "원문 보기 →"; ns="情報源確認中" if ja else "출처 확인 중"
        et   = "ニュースが収集されていません" if ja else "수집된 뉴스가 없습니다"
        es   = "次回の更新をお待ちください" if ja else "다음 업데이트를 기다려주세요"
        cnt  = f"{len(arts)}件" if ja else f"{len(arts)}개 기사"

        badge = f'<span class="tab-badge" style="background:{cat["color"]}">{len(arts)}</span>' if arts else ""
        active_cls = "active" if first else ""
        tabs.append(f'<button class="tab {active_cls}" data-category="{cid}" onclick="showCategory(\'{cid}\')" style="--cat-color:{cat["color"]}"><span class="tab-icon">{cat["icon"]}</span><span class="tab-label">{lbl}</span>{badge}</button>')

        if arts:
            cards = []
            for a in arts:
                imp=a.get("importance","medium")
                ic={"high":"#DC2626","medium":"#D97706","low":"#6B7280"}.get(imp,"#6B7280")
                il2={"high":imp_h,"medium":imp_m,"low":imp_l}.get(imp,imp_m)
                uh=f'<a href="{a["url"]}" target="_blank" rel="noopener noreferrer" class="source-link" style="color:{cat["color"]}">{rm}</a>' if a.get("url") else ""
                cards.append(f'<article class="card" style="border-left-color:{ic}"><div class="card-top"><span class="importance" style="background:{ic}18;color:{ic}">{ip} {il2}</span><span class="date">{a.get("date","")}</span></div><h3 class="card-title">{a.get("title","")}</h3><p class="card-summary">{a.get("summary","")}</p><div class="insight-box"><span class="insight-icon">💡</span><p class="insight-text"><strong>{il_lbl}</strong> {a.get("insight","")}</p></div><div class="card-footer"><span class="source">📌 {a.get("source",ns)}</span>{uh}</div></article>')
            body = "\n".join(cards)
        else:
            body = f'<div class="empty"><div class="empty-icon">{cat["icon"]}</div><p class="empty-title">{et}</p><p class="empty-sub">{es}</p></div>'

        secs.append(f'<section class="category-section {"active" if first else ""}" id="section-{cid}"><div class="cat-header"><div><div class="cat-title-row"><span class="cat-icon">{cat["icon"]}</span><h2 class="cat-title" style="color:{cat["color"]}">{lbl}</h2></div><p class="cat-desc">{dsc}</p></div><span class="article-count">{cnt}</span></div><div class="articles">{body}</div></section>')

    lang_attr = "ja" if ja else "ko"
    tabs_joined = "\n".join(tabs)
    secs_joined = "\n".join(secs)
    return f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OMRON News Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{font_url}" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#F5F6FA;--surface:#fff;--text:#1A1A2E;--text-secondary:#6B7280;--text-muted:#9CA3AF;--border:#E5E7EB}}
body{{font-family:{font_fam};background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}}
header{{background:linear-gradient(135deg,#0A0F1E 0%,#162040 50%,#1A2744 100%);padding:28px 24px 20px;position:relative;overflow:hidden}}
header::before{{content:'';position:absolute;top:-50%;right:-10%;width:400px;height:400px;background:radial-gradient(circle,rgba(0,102,204,.12) 0%,transparent 70%);border-radius:50%}}
.hi{{max-width:1100px;margin:0 auto;position:relative;z-index:1}}
.lr{{display:flex;align-items:center;gap:14px;margin-bottom:16px}}
.lm{{width:46px;height:46px;border-radius:12px;background:linear-gradient(135deg,#0066CC,#00AAFF);display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-weight:700;font-size:17px;color:#fff;letter-spacing:-1px;flex-shrink:0}}
.lt{{flex:1}}.st{{font-size:22px;font-weight:800;color:#fff;letter-spacing:-.5px}}
.ss{{font-size:12px;color:rgba(255,255,255,.55);font-weight:300;margin-top:2px}}
.lang-btn{{display:inline-block;padding:5px 14px;border:1px solid rgba(255,255,255,.3);border-radius:20px;color:rgba(255,255,255,.8);font-size:12px;font-weight:500;text-decoration:none;transition:all .2s;white-space:nowrap}}
.lang-btn:hover{{background:rgba(255,255,255,.15);color:#fff}}
.sr{{display:flex;gap:24px;flex-wrap:wrap;align-items:center}}
.stat{{display:flex;align-items:center;gap:8px}}
.sv{{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:600;color:#fff}}
.sl{{font-size:11px;color:rgba(255,255,255,.5);line-height:1.3}}
.ut{{margin-top:12px;font-size:11px;color:rgba(255,255,255,.35);font-family:'JetBrains Mono',monospace}}
nav{{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.ts{{max-width:1100px;margin:0 auto;display:flex;gap:4px;padding:10px 24px;overflow-x:auto;-webkit-overflow-scrolling:touch}}
.ts::-webkit-scrollbar{{height:0}}
.tab{{display:flex;align-items:center;gap:7px;padding:9px 16px;border-radius:8px;border:1.5px solid transparent;background:transparent;color:var(--text-secondary);font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap;font-family:inherit;transition:all .2s}}
.tab:hover{{background:#F3F4F6}}
.tab.active{{background:color-mix(in srgb,var(--cat-color) 8%,transparent);border-color:var(--cat-color);color:var(--cat-color);font-weight:600}}
.tab-icon{{font-size:17px}}.tab-badge{{font-size:10px;font-weight:700;color:#fff;border-radius:10px;padding:1px 7px;min-width:18px;text-align:center}}
main{{max-width:1100px;margin:0 auto;padding:24px}}
.category-section{{display:none;animation:fi .3s ease}}.category-section.active{{display:block}}
@keyframes fi{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.cat-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;flex-wrap:wrap;gap:12px}}
.cat-title-row{{display:flex;align-items:center;gap:10px}}.cat-icon{{font-size:28px}}
.cat-title{{font-size:22px;font-weight:800;letter-spacing:-.5px}}
.cat-desc{{font-size:13px;color:var(--text-secondary);margin-top:3px}}
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
@media(max-width:640px){{header{{padding:20px 16px}}.st{{font-size:18px}}main{{padding:16px}}.card{{padding:16px}}.cat-title{{font-size:18px}}.tab{{padding:7px 12px;font-size:12px}}}}
</style></head><body>
<header><div class="hi">
<div class="lr"><div class="lm">ON</div><div class="lt"><h1 class="st">OMRON News Intelligence</h1><p class="ss">{sub}</p></div>{lang_btn}</div>
<div class="sr"><div class="stat"><span class="sv">{total}</span><span class="sl">{al}</span></div><div class="stat"><span class="sv">{high}</span><span class="sl">{hl}</span></div><div class="stat"><span class="sv">{len(CATEGORIES)}</span><span class="sl">{cl}</span></div></div>
<p class="ut">{ul} {update_time}</p>
</div></header>
<nav><div class="ts">{tabs_joined}</div></nav>
<main>{secs_joined}</main>
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
    print("="*55); print("OMRON News Intelligence"); print("="*55)
    kst = timezone(timedelta(hours=9)); now = datetime.now(kst)
    t_ko = now.strftime("%Y년 %m월 %d일 %H:%M KST")
    t_ja = now.strftime("%Y年%m月%d日 %H:%M KST")
    if not API_KEY: print("API_KEY 없음!"); sys.exit(1)
    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(out, exist_ok=True)

    # 1단계: 한국어 수집
    print("\n[ 1단계: 한국어 수집 ]")
    news_ko = {}
    for i, cat in enumerate(CATEGORIES):
        print(f"\n[{i+1}/6] {cat['icon']} {cat['ko']}...")
        news_ko[cat["id"]] = fetch_ko(cat)
        if i < len(CATEGORIES)-1:
            print(f"  ⏸ 다음 카테고리까지 12초 대기...")
            time.sleep(12)

    # 2단계: 일본어 번역
    print("\n[ 2단계: 일본어 번역 ]")
    news_ja = {}
    for i, cat in enumerate(CATEGORIES):
        arts = news_ko.get(cat["id"],[])
        if arts:
            print(f"\n[{i+1}/6] {cat['icon']} {cat['ja']} 번역...")
            news_ja[cat["id"]] = translate_category(arts, cat["ja"])
            time.sleep(2)
        else:
            print(f"\n[{i+1}/6] {cat['icon']} {cat['ja']} — 기사 없음")
            news_ja[cat["id"]] = []

    # 3단계: HTML 저장
    print("\n[ 3단계: HTML 생성 ]")
    with open(os.path.join(out,"index.html"),"w",encoding="utf-8") as f:
        f.write(make_html(news_ko, t_ko, lang="ko", other_url="index_ja.html"))
    with open(os.path.join(out,"index_ja.html"),"w",encoding="utf-8") as f:
        f.write(make_html(news_ja, t_ja, lang="ja", other_url="index.html"))

    tk = sum(len(v) for v in news_ko.values())
    tj = sum(len(v) for v in news_ja.values())
    print(f"\n완료! 한국어 {tk}개 / 일본어 {tj}개")
    print("="*55)

if __name__ == "__main__":
    main()
