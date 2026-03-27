#!/usr/bin/env python3
"""
OMRON News Intelligence - 뉴스 수집 및 정적 HTML 생성 스크립트
- 한국어 (docs/index.html) + 일본어 (docs/index_ja.html) 동시 생성
- Claude Haiku 모델 사용 (비용 절감)
- 멀티턴 tool_use 처리 수정 (전 카테고리 수집 가능)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("requests 패키지가 없습니다. pip install requests 로 설치하세요.")
    sys.exit(1)

# ========== 설정 ==========
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"

# ✅ Haiku로 교체 — Sonnet 대비 약 85% 비용 절감
MODEL = "claude-3-5-haiku-20241022"

# ========== 한국어 카테고리 ==========
CATEGORIES_KO = [
    {
        "id": "omron",
        "label": "OMRON 소식",
        "icon": "🏢",
        "color": "#0066CC",
        "queries": ["Omron Corporation news 2026", "오므론 전자부품 최신 뉴스"],
        "description": "오므론 본사 및 글로벌 소식",
    },
    {
        "id": "hfe",
        "label": "HFE",
        "icon": "📡",
        "color": "#7C3AED",
        "queries": [
            "semiconductor inspection equipment news 2026",
            "카메라모듈 디스플레이 모바일 검사장비 뉴스",
            "반도체 생산 검사 장비 업계 동향 2026",
        ],
        "description": "고주파장비 · 모바일검사 · 반도체장비",
    },
    {
        "id": "dce",
        "label": "DCE",
        "icon": "⚡",
        "color": "#059669",
        "queries": [
            "LG에너지솔루션 SK온 삼성SDI 배터리 뉴스 2026",
            "ESS 에너지저장 데이터센터 전력 뉴스 2026",
            "DC power equipment high power industry",
        ],
        "description": "DC파워 · 배터리 · ESS · 데이터센터",
    },
    {
        "id": "appliance",
        "label": "가전업계",
        "icon": "🏠",
        "color": "#DC2626",
        "queries": [
            "LG전자 삼성전자 가전제품 신제품 뉴스 2026",
            "Korea home appliance industry news 2026",
        ],
        "description": "LG · 삼성 가전제품 동향",
    },
    {
        "id": "casino",
        "label": "카지노 머신",
        "icon": "🎰",
        "color": "#D97706",
        "queries": [
            "casino slot machine gaming industry news 2026",
            "gaming machine component market Asia",
        ],
        "description": "카지노 머신 · 게이밍 장비",
    },
    {
        "id": "electronics",
        "label": "전자산업 동향",
        "icon": "🔌",
        "color": "#0891B2",
        "queries": [
            "한국 전자산업 동향 뉴스 2026",
            "electronic component relay switch connector market Korea 2026",
        ],
        "description": "릴레이 · 스위치 · 커넥터 범용부품 산업",
    },
]

# ========== 일본어 카테고리 ==========
CATEGORIES_JA = [
    {
        "id": "omron",
        "label": "オムロン情報",
        "icon": "🏢",
        "color": "#0066CC",
        "queries": ["Omron Corporation news 2026", "オムロン電子部品 最新ニュース 2026"],
        "description": "オムロン本社・グローバルニュース",
    },
    {
        "id": "hfe",
        "label": "HFE",
        "icon": "📡",
        "color": "#7C3AED",
        "queries": [
            "半導体検査装置 最新ニュース 2026",
            "カメラモジュール ディスプレイ 検査装置 業界動向",
            "semiconductor inspection equipment news 2026",
        ],
        "description": "高周波装置・モバイル検査・半導体装置",
    },
    {
        "id": "dce",
        "label": "DCE",
        "icon": "⚡",
        "color": "#059669",
        "queries": [
            "リチウムイオン電池 ESS データセンター電力 ニュース 2026",
            "LG Energy Solution Samsung SDI battery news 2026",
            "DCパワー 大電力機器 業界動向 2026",
        ],
        "description": "DCパワー・バッテリー・ESS・データセンター",
    },
    {
        "id": "appliance",
        "label": "家電業界",
        "icon": "🏠",
        "color": "#DC2626",
        "queries": [
            "LG電子 サムスン電子 家電製品 新製品 ニュース 2026",
            "Korea Japan home appliance industry news 2026",
        ],
        "description": "LG・サムスン 家電製品動向",
    },
    {
        "id": "casino",
        "label": "カジノ機器",
        "icon": "🎰",
        "color": "#D97706",
        "queries": [
            "casino slot machine gaming industry news 2026",
            "ゲーミングマシン 電子部品 アジア市場 2026",
        ],
        "description": "カジノ機器・ゲーミング装置",
    },
    {
        "id": "electronics",
        "label": "電子産業動向",
        "icon": "🔌",
        "color": "#0891B2",
        "queries": [
            "電子部品 リレー スイッチ コネクタ 市場動向 2026",
            "electronic component market Japan Korea 2026",
        ],
        "description": "リレー・スイッチ・コネクタ 汎用部品産業",
    },
]

# ========== 시스템 프롬프트 ==========
SYSTEM_PROMPT_KO = """당신은 전자부품 산업 전문 뉴스 분석가입니다. 오므론전자부품(Omron Electronic Components) 기술영업팀을 위해 주간 뉴스를 분석합니다.

검색 결과를 바탕으로 다음 형식의 JSON만 반환하세요. 절대 다른 텍스트를 포함하지 마세요:

{
  "articles": [
    {
      "title": "기사 제목 (한국어로)",
      "summary": "3-4문장으로 핵심 내용 요약 (한국어로). 오므론 영업팀 관점에서 중요한 포인트를 강조",
      "insight": "이 뉴스가 오므론 전자부품 영업에 미치는 영향이나 기회를 1-2문장으로 (한국어로)",
      "source": "출처명",
      "url": "기사 URL (실제 확인된 것만)",
      "date": "YYYY-MM-DD 또는 빈 문자열",
      "importance": "high 또는 medium 또는 low"
    }
  ]
}

규칙:
- 반드시 유효한 JSON만 출력 (마크다운 코드블록 없이)
- 최대 5개 기사
- 모든 텍스트는 한국어로
- importance는 오므론 전자부품 영업 관점에서의 중요도
- 【우선순위】이번 주(최근 7일 이내) 새로운 발표·출시·정책 변경·실적 발표가 있는 기사를 반드시 최우선 선별하고, 해당 주간 신규 업데이트가 없는 경우에만 최근 1개월 내 주요 뉴스로 보완할 것
- 날짜가 오래된 뉴스보다 이번 주 신규 내용을 항상 위에 배치"""

SYSTEM_PROMPT_JA = """あなたは電子部品産業の専門ニュースアナリストです。オムロン電子部品(Omron Electronic Components)の技術営業チームのために週間ニュースを分析します。

検索結果をもとに、以下のJSON形式のみを返してください。他のテキストは絶対に含めないでください:

{
  "articles": [
    {
      "title": "記事タイトル（日本語で）",
      "summary": "3〜4文で主要内容を要約（日本語で）。オムロン営業チームの視点から重要なポイントを強調",
      "insight": "このニュースがオムロン電子部品の営業に与える影響・機会を1〜2文で（日本語で）",
      "source": "情報源名",
      "url": "記事URL（確認済みのもののみ）",
      "date": "YYYY-MM-DD または空文字",
      "importance": "high または medium または low"
    }
  ]
}

ルール:
- 必ず有効なJSONのみ出力（マークダウンコードブロックなし）
- 最大5件の記事
- すべてのテキストは日本語で
- importanceはオムロン電子部品営業観点での重要度
- 【優先順位】今週（直近7日以内）の新発表・新製品・政策変更・決算発表がある記事を必ず最優先で選定し、該当する週次新規情報がない場合のみ直近1ヶ月以内の主要ニュースで補完すること
- 日付が古いニュースより今週の新規情報を常に上位に配置"""


# ========== API 호출 (멀티턴 처리 포함) ==========
def fetch_news_for_category(category, system_prompt, max_retries=2):
    """
    Claude API를 사용해 뉴스를 수집합니다.
    web_search 도구의 멀티턴(tool_use → tool_result) 흐름을 올바르게 처리합니다.
    """
    if not ANTHROPIC_API_KEY:
        print("  ⚠️ API 키가 설정되지 않았습니다.")
        return []

    query_text = ", ".join(category["queries"])

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 10 * attempt
            print(f"  ↻ 재시도 {attempt}/{max_retries} ({wait}초 대기 후)...")
            time.sleep(wait)

        try:
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"이번 주(최근 7일 이내) 신규 발표·출시·정책 변경을 최우선으로, "
                        f"없으면 최근 1개월 내 주요 뉴스 순으로 다음 주제를 검색하고 분석해주세요: {query_text}\n\n"
                        f"카테고리: {category['label']} ({category['description']})"
                    ),
                }
            ]

            # ✅ 멀티턴 루프 — tool_use 응답이 올 때마다 계속 이어서 요청
            max_turns = 8
            for turn in range(max_turns):
                payload = {
                    "model": MODEL,
                    "max_tokens": 4000,
                    "system": system_prompt,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": messages,
                }

                resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()

                stop_reason = data.get("stop_reason", "")
                content_blocks = data.get("content", [])

                # 어시스턴트 응답을 메시지 히스토리에 추가
                messages.append({"role": "assistant", "content": content_blocks})

                # 텍스트 블록 추출
                text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]

                if stop_reason == "end_turn":
                    # 최종 응답 — JSON 파싱
                    full_text = " ".join(text_parts)
                    return _parse_articles(full_text, category["label"])

                elif stop_reason == "tool_use":
                    # 웹 검색 도구 호출 → tool_result로 응답 이어가기
                    tool_results = []
                    for block in content_blocks:
                        if block.get("type") == "tool_use":
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": "Tool executed successfully.",
                            })
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})
                    else:
                        # tool_use 블록이 없으면 텍스트라도 파싱 시도
                        full_text = " ".join(text_parts)
                        return _parse_articles(full_text, category["label"])

                else:
                    # max_tokens 등 기타 stop_reason
                    full_text = " ".join(text_parts)
                    if full_text:
                        return _parse_articles(full_text, category["label"])
                    break

            print(f"  ⚠️ 최대 턴({max_turns}) 도달 — 빈 결과 반환")
            return []

        except requests.exceptions.Timeout:
            print(f"  ⏱ 타임아웃 발생 (시도 {attempt+1})")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            print(f"  ❌ HTTP 오류 {status}: {e}")
            if status == 429:
                print("  ⏳ 속도 제한 — 30초 대기...")
                time.sleep(30)
        except Exception as e:
            print(f"  ❌ 오류: {e}")

    return []


def _parse_articles(text, label):
    """응답 텍스트에서 JSON 기사 목록을 추출합니다."""
    if not text.strip():
        print(f"  ⚠️ {label}: 빈 응답")
        return []

    cleaned = text.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    if start == -1:
        print(f"  ⚠️ {label}: JSON 없음 — 응답: {cleaned[:200]}")
        return []

    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(cleaned[start: i + 1])
                    articles = parsed.get("articles", [])
                    print(f"  ✅ {len(articles)}개 기사 수집 완료")
                    return articles
                except json.JSONDecodeError as e:
                    print(f"  ❌ JSON 파싱 오류: {e}")
                    return []
    print(f"  ⚠️ {label}: JSON 괄호 불균형")
    return []


# ========== HTML 생성 ==========
def generate_html(all_news, update_time, categories, lang="ko", other_lang_url=None):
    """수집된 뉴스로 정적 HTML 파일을 생성합니다."""

    is_ja = (lang == "ja")
    html_lang = "ja" if is_ja else "ko"
    font_family = "'Noto Sans JP', 'Noto Sans KR', -apple-system, sans-serif" if is_ja else "'Noto Sans KR', -apple-system, sans-serif"
    google_font = (
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;600;700;800"
        "&family=JetBrains+Mono:wght@400;500;600&display=swap"
        if is_ja else
        "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800"
        "&family=JetBrains+Mono:wght@400;500;600&display=swap"
    )

    # 언어 전환 버튼
    if other_lang_url:
        lang_btn_label = "한국어" if is_ja else "日本語"
        lang_switcher_html = f'<a href="{other_lang_url}" class="lang-btn">{lang_btn_label}</a>'
    else:
        lang_switcher_html = ""

    # 카테고리별 탭·섹션 생성
    tab_buttons = []
    category_sections = []

    for idx, cat in enumerate(categories):
        cat_id = cat["id"]
        articles = all_news.get(cat_id, [])
        is_first = idx == 0

        tab_buttons.append(
            f"""<button class="tab {'active' if is_first else ''}"
                    data-category="{cat_id}"
                    onclick="showCategory('{cat_id}')"
                    style="--cat-color: {cat['color']}">
                <span class="tab-icon">{cat['icon']}</span>
                <span class="tab-label">{cat['label']}</span>
                {f'<span class="tab-badge" style="background:{cat["color"]}">{len(articles)}</span>' if articles else ''}
            </button>"""
        )

        article_cards = []
        if articles:
            for art in articles:
                imp = art.get("importance", "medium")
                if is_ja:
                    imp_label = {"high": "高", "medium": "中", "low": "低"}.get(imp, "中")
                    imp_prefix = "重要度:"
                    insight_label = "営業インサイト:"
                    source_prefix = "📌"
                    read_more = "記事を読む →"
                else:
                    imp_label = {"high": "높음", "medium": "보통", "low": "낮음"}.get(imp, "보통")
                    imp_prefix = "중요도:"
                    insight_label = "영업 인사이트:"
                    source_prefix = "📌"
                    read_more = "원문 보기 →"

                imp_color = {"high": "#DC2626", "medium": "#D97706", "low": "#6B7280"}.get(imp, "#6B7280")

                url_html = ""
                if art.get("url"):
                    url_html = f'<a href="{art["url"]}" target="_blank" rel="noopener noreferrer" class="source-link" style="color:{cat["color"]}">{read_more}</a>'

                article_cards.append(
                    f"""<article class="card" style="border-left-color: {imp_color}">
                    <div class="card-top">
                        <span class="importance" style="background:{imp_color}18;color:{imp_color}">{imp_prefix} {imp_label}</span>
                        <span class="date">{art.get('date', '')}</span>
                    </div>
                    <h3 class="card-title">{art.get('title', '')}</h3>
                    <p class="card-summary">{art.get('summary', '')}</p>
                    <div class="insight-box">
                        <span class="insight-icon">💡</span>
                        <p class="insight-text"><strong>{insight_label}</strong> {art.get('insight', '')}</p>
                    </div>
                    <div class="card-footer">
                        <span class="source">{source_prefix} {art.get('source', '출처 확인 중' if not is_ja else '情報源確認中')}</span>
                        {url_html}
                    </div>
                </article>"""
                )
            articles_html = "\n".join(article_cards)
        else:
            if is_ja:
                empty_title = "ニュースが収集されていません"
                empty_sub = "次回の更新をお待ちください"
            else:
                empty_title = "수집된 뉴스가 없습니다"
                empty_sub = "다음 업데이트를 기다려주세요"
            articles_html = f"""<div class="empty">
                <div class="empty-icon">{cat['icon']}</div>
                <p class="empty-title">{empty_title}</p>
                <p class="empty-sub">{empty_sub}</p>
            </div>"""

        art_count_label = f"{len(articles)}件" if is_ja else f"{len(articles)}개 기사"
        category_sections.append(
            f"""<section class="category-section {'active' if is_first else ''}" id="section-{cat_id}">
            <div class="cat-header">
                <div>
                    <div class="cat-title-row">
                        <span class="cat-icon">{cat['icon']}</span>
                        <h2 class="cat-title" style="color:{cat['color']}">{cat['label']}</h2>
                    </div>
                    <p class="cat-desc">{cat['description']}</p>
                </div>
                <span class="article-count">{art_count_label}</span>
            </div>
            <div class="articles">{articles_html}</div>
        </section>"""
        )

    tabs_html = "\n".join(tab_buttons)
    sections_html = "\n".join(category_sections)

    total_articles = sum(len(all_news.get(c["id"], [])) for c in categories)
    high_count = sum(
        1 for c in categories for a in all_news.get(c["id"], [])
        if a.get("importance") == "high"
    )

    if is_ja:
        site_title = "OMRON News Intelligence"
        # ✅ 수정된 서브타이틀 (일본어)
        site_subtitle = "オムロン電子部品 社員の皆様のための産業ニュースダッシュボード"
        articles_label = "本日の記事"
        high_label = "重要度: 高"
        category_label = "カテゴリ数"
        update_label = "週間更新:"
        # ✅ 수정된 푸터 (일본어)
        footer_text = "Powered by Claude AI · オムロン電子部品 Choi Hongsun · 毎週月曜日 午前6時自動更新"
    else:
        site_title = "OMRON News Intelligence"
        # ✅ 수정된 서브타이틀 (한국어)
        site_subtitle = "오므론전자부품 사우분들을 위한 산업 뉴스 대시보드"
        articles_label = "오늘의 기사"
        high_label = "높은 중요도"
        category_label = "분석 카테고리"
        update_label = "주간 업데이트:"
        # ✅ 수정된 푸터 (한국어)
        footer_text = "Powered by Claude AI · 오므론전자부품 최홍선 · 매주 월요일 오전 6시 자동 업데이트"

    html = f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OMRON News Intelligence</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="{google_font}" rel="stylesheet">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        :root {{
            --bg: #F5F6FA;
            --surface: #FFFFFF;
            --text: #1A1A2E;
            --text-secondary: #6B7280;
            --text-muted: #9CA3AF;
            --border: #E5E7EB;
            --header-bg: linear-gradient(135deg, #0A0F1E 0%, #162040 50%, #1A2744 100%);
            --omron-blue: #0066CC;
        }}
        body {{
            font-family: {font_family};
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        header {{
            background: var(--header-bg);
            padding: 28px 24px 20px;
            position: relative;
            overflow: hidden;
        }}
        header::before {{
            content: '';
            position: absolute;
            top: -50%; right: -10%;
            width: 400px; height: 400px;
            background: radial-gradient(circle, rgba(0,102,204,0.12) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .header-inner {{
            max-width: 1100px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }}
        .logo-row {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 16px;
        }}
        .logo-mark {{
            width: 46px; height: 46px;
            border-radius: 12px;
            background: linear-gradient(135deg, #0066CC, #00AAFF);
            display: flex; align-items: center; justify-content: center;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700; font-size: 17px;
            color: #fff; letter-spacing: -1px; flex-shrink: 0;
        }}
        .logo-text {{ flex: 1; }}
        .site-title {{
            font-size: 22px; font-weight: 800;
            color: #FFFFFF; letter-spacing: -0.5px;
        }}
        .site-subtitle {{
            font-size: 12px;
            color: rgba(255,255,255,0.55);
            font-weight: 300; margin-top: 2px;
        }}
        .lang-btn {{
            display: inline-block;
            padding: 5px 14px;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 20px;
            color: rgba(255,255,255,0.8);
            font-size: 12px;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .lang-btn:hover {{
            background: rgba(255,255,255,0.15);
            color: #fff;
        }}
        .stats-row {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .stat {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px; font-weight: 600;
            color: #FFFFFF;
        }}
        .stat-label {{
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            line-height: 1.3;
        }}
        .update-time {{
            margin-top: 12px;
            font-size: 11px;
            color: rgba(255,255,255,0.35);
            font-family: 'JetBrains Mono', monospace;
        }}
        nav {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .tab-scroll {{
            max-width: 1100px; margin: 0 auto;
            display: flex; gap: 4px;
            padding: 10px 24px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .tab-scroll::-webkit-scrollbar {{ height: 0; }}
        .tab {{
            display: flex; align-items: center; gap: 7px;
            padding: 9px 16px;
            border-radius: 8px;
            border: 1.5px solid transparent;
            background: transparent;
            color: var(--text-secondary);
            font-size: 13px; font-weight: 500;
            cursor: pointer; white-space: nowrap;
            font-family: inherit;
            transition: all 0.2s;
        }}
        .tab:hover {{ background: #F3F4F6; }}
        .tab.active {{
            background: color-mix(in srgb, var(--cat-color) 8%, transparent);
            border-color: var(--cat-color);
            color: var(--cat-color);
            font-weight: 600;
        }}
        .tab-icon {{ font-size: 17px; }}
        .tab-badge {{
            font-size: 10px; font-weight: 700;
            color: #fff; border-radius: 10px;
            padding: 1px 7px; min-width: 18px;
            text-align: center;
        }}
        main {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px;
        }}
        .category-section {{ display: none; animation: fadeIn 0.3s ease; }}
        .category-section.active {{ display: block; }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .cat-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .cat-title-row {{
            display: flex; align-items: center; gap: 10px;
        }}
        .cat-icon {{ font-size: 28px; }}
        .cat-title {{
            font-size: 22px; font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .cat-desc {{
            font-size: 13px; color: var(--text-secondary); margin-top: 3px;
        }}
        .article-count {{
            font-size: 12px; color: var(--text-muted);
            background: #F3F4F6; padding: 4px 12px;
            border-radius: 20px; font-weight: 500;
        }}
        .articles {{ display: flex; flex-direction: column; gap: 14px; }}
        .card {{
            background: var(--surface);
            border-radius: 12px;
            padding: 20px 24px;
            border-left: 4px solid;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            transition: all 0.2s;
        }}
        .card:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.07);
        }}
        .card-top {{
            display: flex; justify-content: space-between;
            align-items: center; margin-bottom: 10px;
        }}
        .importance {{
            font-size: 11px; font-weight: 600;
            padding: 3px 10px; border-radius: 20px;
        }}
        .date {{
            font-size: 12px; color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}
        .card-title {{
            font-size: 16px; font-weight: 700;
            color: #111827; line-height: 1.45;
            margin-bottom: 10px; letter-spacing: -0.3px;
        }}
        .card-summary {{
            font-size: 13.5px; color: #4B5563;
            line-height: 1.75; margin-bottom: 14px;
        }}
        .insight-box {{
            display: flex; gap: 8px;
            background: #FFFBEB;
            border: 1px solid #FDE68A;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }}
        .insight-icon {{ font-size: 16px; flex-shrink: 0; margin-top: 1px; }}
        .insight-text {{ font-size: 12.5px; color: #92400E; line-height: 1.65; }}
        .card-footer {{
            display: flex; justify-content: space-between;
            align-items: center;
            padding-top: 10px;
            border-top: 1px solid #F3F4F6;
        }}
        .source {{ font-size: 12px; color: var(--text-muted); }}
        .source-link {{
            font-size: 12px; font-weight: 600;
            text-decoration: none; transition: opacity 0.2s;
        }}
        .source-link:hover {{ opacity: 0.7; }}
        .empty {{
            text-align: center; padding: 60px 20px;
        }}
        .empty-icon {{ font-size: 48px; opacity: 0.3; margin-bottom: 12px; }}
        .empty-title {{ font-size: 15px; font-weight: 600; color: #374151; }}
        .empty-sub {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
        footer {{
            text-align: center;
            padding: 28px 24px;
            font-size: 11px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            margin-top: 48px;
        }}
        @media (max-width: 640px) {{
            header {{ padding: 20px 16px; }}
            .site-title {{ font-size: 18px; }}
            main {{ padding: 16px; }}
            .card {{ padding: 16px; }}
            .cat-title {{ font-size: 18px; }}
            .tab {{ padding: 7px 12px; font-size: 12px; }}
        }}
    </style>
</head>
<body>

<header>
    <div class="header-inner">
        <div class="logo-row">
            <div class="logo-mark">ON</div>
            <div class="logo-text">
                <h1 class="site-title">{site_title}</h1>
                <p class="site-subtitle">{site_subtitle}</p>
            </div>
            {lang_switcher_html}
        </div>
        <div class="stats-row">
            <div class="stat">
                <span class="stat-value">{total_articles}</span>
                <span class="stat-label">{articles_label}</span>
            </div>
            <div class="stat">
                <span class="stat-value">{high_count}</span>
                <span class="stat-label">{high_label}</span>
            </div>
            <div class="stat">
                <span class="stat-value">{len(categories)}</span>
                <span class="stat-label">{category_label}</span>
            </div>
        </div>
        <p class="update-time">{update_label} {update_time}</p>
    </div>
</header>

<nav>
    <div class="tab-scroll">
        {tabs_html}
    </div>
</nav>

<main>
    {sections_html}
</main>

<footer>
    {footer_text}
</footer>

<script>
function showCategory(id) {{
    document.querySelectorAll('.category-section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('section-' + id).classList.add('active');
    document.querySelector('[data-category="' + id + '"]').classList.add('active');
}}
</script>
</body>
</html>"""
    return html


# ========== 메인 ==========
def main():
    print("=" * 55)
    print("🏢 OMRON News Intelligence — 뉴스 수집 시작")
    print("=" * 55)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    update_time_ko = now.strftime("%Y년 %m월 %d일 %H:%M KST")
    update_time_ja = now.strftime("%Y年%m月%d日 %H:%M KST")
    print(f"⏰ 현재 시각: {update_time_ko}\n")

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다!")
        sys.exit(1)

    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(output_dir, exist_ok=True)

    # ── 한국어 페이지 수집 ──
    print("\n[ 한국어 페이지 수집 시작 ]")
    all_news_ko = {}
    for i, cat in enumerate(CATEGORIES_KO):
        print(f"\n[KO {i+1}/{len(CATEGORIES_KO)}] {cat['icon']} {cat['label']} 수집 중...")
        all_news_ko[cat["id"]] = fetch_news_for_category(cat, SYSTEM_PROMPT_KO)
        if i < len(CATEGORIES_KO) - 1:
            time.sleep(5)  # API 부하 방지

    # ── 일본어 페이지 수집 ──
    print("\n\n[ 일본어 페이지 수집 시작 ]")
    all_news_ja = {}
    for i, cat in enumerate(CATEGORIES_JA):
        print(f"\n[JA {i+1}/{len(CATEGORIES_JA)}] {cat['icon']} {cat['label']} 収集中...")
        all_news_ja[cat["id"]] = fetch_news_for_category(cat, SYSTEM_PROMPT_JA)
        if i < len(CATEGORIES_JA) - 1:
            time.sleep(5)

    # ── HTML 생성 ──
    print("\n\n📄 HTML 파일 생성 중...")

    ko_path = os.path.join(output_dir, "index.html")
    ja_path = os.path.join(output_dir, "index_ja.html")

    html_ko = generate_html(
        all_news_ko, update_time_ko,
        CATEGORIES_KO, lang="ko",
        other_lang_url="index_ja.html"
    )
    html_ja = generate_html(
        all_news_ja, update_time_ja,
        CATEGORIES_JA, lang="ja",
        other_lang_url="index.html"
    )

    with open(ko_path, "w", encoding="utf-8") as f:
        f.write(html_ko)
    with open(ja_path, "w", encoding="utf-8") as f:
        f.write(html_ja)

    total_ko = sum(len(v) for v in all_news_ko.values())
    total_ja = sum(len(v) for v in all_news_ja.values())

    print(f"\n✅ 완료!")
    print(f"   한국어: {total_ko}개 기사 → {ko_path}")
    print(f"   일본어: {total_ja}件 記事 → {ja_path}")
    print("=" * 55)


if __name__ == "__main__":
    main()
