#!/usr/bin/env python3
"""
OMRON News Intelligence - 뉴스 수집 및 정적 HTML 생성 스크립트
매일 GitHub Actions에서 실행되어 Claude API로 뉴스를 수집하고
정적 HTML 파일을 생성합니다.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("requests 패키지가 없습니다. pip install requests 로 설치하세요.")
    sys.exit(1)

# ========== 설정 ==========

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

CATEGORIES = [
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

SYSTEM_PROMPT = """당신은 전자부품 산업 전문 뉴스 분석가입니다. 오므론전자부품(Omron Electronic Components) 기술영업팀을 위해 뉴스를 분석합니다.

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
- 가능한 최신 뉴스를 우선"""


def fetch_news_for_category(category):
    """Claude API를 사용하여 특정 카테고리의 뉴스를 수집합니다."""
    if not ANTHROPIC_API_KEY:
        print(f"  ⚠️ API 키가 설정되지 않았습니다.")
        return []

    query_text = ", ".join(category["queries"])

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": MODEL,
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [
            {
                "role": "user",
                "content": f"다음 주제에 대한 최신 뉴스를 검색하고 분석해주세요: {query_text}\n\n카테고리: {category['label']} ({category['description']})",
            }
        ],
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        # 텍스트 블록에서 JSON 추출
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])

        full_text = " ".join(text_parts)

        # JSON 파싱
        cleaned = full_text.replace("```json", "").replace("```", "").strip()
        json_match = None
        # { 로 시작하는 JSON 객체 찾기
        start = cleaned.find("{")
        if start != -1:
            # 중첩 괄호를 고려한 간단한 파서
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                    if depth == 0:
                        json_match = cleaned[start : i + 1]
                        break

        if json_match:
            parsed = json.loads(json_match)
            articles = parsed.get("articles", [])
            print(f"  ✅ {len(articles)}개 기사 수집 완료")
            return articles
        else:
            print(f"  ⚠️ JSON을 찾을 수 없습니다")
            print(f"  응답: {full_text[:300]}")
            return []

    except requests.exceptions.RequestException as e:
        print(f"  ❌ API 요청 오류: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 파싱 오류: {e}")
        return []
    except Exception as e:
        print(f"  ❌ 예상치 못한 오류: {e}")
        return []


def generate_html(all_news, update_time):
    """수집된 뉴스로 정적 HTML 파일을 생성합니다."""

    # 각 카테고리별 기사 HTML 생성
    category_sections = []
    tab_buttons = []

    for cat in CATEGORIES:
        cat_id = cat["id"]
        articles = all_news.get(cat_id, [])
        is_first = cat == CATEGORIES[0]

        # 탭 버튼
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

        # 기사 카드들
        article_cards = []
        if articles:
            for art in articles:
                imp = art.get("importance", "medium")
                imp_label = {"high": "높음", "medium": "보통", "low": "낮음"}.get(
                    imp, "보통"
                )
                imp_color = {"high": "#DC2626", "medium": "#D97706", "low": "#6B7280"}.get(
                    imp, "#6B7280"
                )

                url_html = ""
                if art.get("url"):
                    url_html = f'<a href="{art["url"]}" target="_blank" rel="noopener noreferrer" class="source-link" style="color:{cat["color"]}">원문 보기 →</a>'

                article_cards.append(
                    f"""<article class="card" style="border-left-color: {imp_color}">
                    <div class="card-top">
                        <span class="importance" style="background:{imp_color}18;color:{imp_color}">중요도: {imp_label}</span>
                        <span class="date">{art.get('date', '')}</span>
                    </div>
                    <h3 class="card-title">{art.get('title', '')}</h3>
                    <p class="card-summary">{art.get('summary', '')}</p>
                    <div class="insight-box">
                        <span class="insight-icon">💡</span>
                        <p class="insight-text"><strong>영업 인사이트:</strong> {art.get('insight', '')}</p>
                    </div>
                    <div class="card-footer">
                        <span class="source">📌 {art.get('source', '출처 확인 중')}</span>
                        {url_html}
                    </div>
                </article>"""
                )
            articles_html = "\n".join(article_cards)
        else:
            articles_html = f"""<div class="empty">
                <div class="empty-icon">{cat['icon']}</div>
                <p class="empty-title">수집된 뉴스가 없습니다</p>
                <p class="empty-sub">다음 업데이트를 기다려주세요</p>
            </div>"""

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
                <span class="article-count">{len(articles)}개 기사</span>
            </div>
            <div class="articles">{articles_html}</div>
        </section>"""
        )

    tabs_html = "\n".join(tab_buttons)
    sections_html = "\n".join(category_sections)

    # 전체 기사 수
    total_articles = sum(len(all_news.get(c["id"], [])) for c in CATEGORIES)
    high_count = sum(
        1
        for c in CATEGORIES
        for a in all_news.get(c["id"], [])
        if a.get("importance") == "high"
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OMRON News Intelligence</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
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
            font-family: 'Noto Sans KR', -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        
        /* HEADER */
        header {{
            background: var(--header-bg);
            padding: 28px 24px 20px;
            position: relative;
            overflow: hidden;
        }}
        header::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 400px;
            height: 400px;
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
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: linear-gradient(135deg, #0066CC, #00AAFF);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 17px;
            color: #fff;
            letter-spacing: -1px;
            flex-shrink: 0;
        }}
        .site-title {{
            font-size: 22px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: -0.5px;
        }}
        .site-subtitle {{
            font-size: 12px;
            color: rgba(255,255,255,0.45);
            font-weight: 300;
            margin-top: 2px;
        }}
        .stats-row {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
        }}
        .stat {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 600;
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
        
        /* NAV TABS */
        nav {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .tab-scroll {{
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            gap: 4px;
            padding: 10px 24px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .tab-scroll::-webkit-scrollbar {{ height: 0; }}
        .tab {{
            display: flex;
            align-items: center;
            gap: 7px;
            padding: 9px 16px;
            border-radius: 8px;
            border: 1.5px solid transparent;
            background: transparent;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            white-space: nowrap;
            font-family: 'Noto Sans KR', sans-serif;
            transition: all 0.2s;
        }}
        .tab:hover {{
            background: #F3F4F6;
        }}
        .tab.active {{
            background: color-mix(in srgb, var(--cat-color) 8%, transparent);
            border-color: var(--cat-color);
            color: var(--cat-color);
            font-weight: 600;
        }}
        .tab-icon {{ font-size: 17px; }}
        .tab-badge {{
            font-size: 10px;
            font-weight: 700;
            color: #fff;
            border-radius: 10px;
            padding: 1px 7px;
            min-width: 18px;
            text-align: center;
        }}
        
        /* MAIN */
        main {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px;
        }}
        .category-section {{
            display: none;
            animation: fadeIn 0.3s ease;
        }}
        .category-section.active {{
            display: block;
        }}
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
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .cat-icon {{ font-size: 28px; }}
        .cat-title {{
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .cat-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 3px;
        }}
        .article-count {{
            font-size: 12px;
            color: var(--text-muted);
            background: #F3F4F6;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 500;
        }}
        
        /* CARDS */
        .articles {{
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .importance {{
            font-size: 11px;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
        }}
        .date {{
            font-size: 12px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}
        .card-title {{
            font-size: 16px;
            font-weight: 700;
            color: #111827;
            line-height: 1.45;
            margin-bottom: 10px;
            letter-spacing: -0.3px;
        }}
        .card-summary {{
            font-size: 13.5px;
            color: #4B5563;
            line-height: 1.75;
            margin-bottom: 14px;
        }}
        .insight-box {{
            display: flex;
            gap: 8px;
            background: #FFFBEB;
            border: 1px solid #FDE68A;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }}
        .insight-icon {{
            font-size: 16px;
            flex-shrink: 0;
            margin-top: 1px;
        }}
        .insight-text {{
            font-size: 12.5px;
            color: #92400E;
            line-height: 1.65;
        }}
        .card-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 10px;
            border-top: 1px solid #F3F4F6;
        }}
        .source {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        .source-link {{
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: opacity 0.2s;
        }}
        .source-link:hover {{ opacity: 0.7; }}
        
        /* EMPTY STATE */
        .empty {{
            text-align: center;
            padding: 60px 20px;
        }}
        .empty-icon {{ font-size: 48px; opacity: 0.3; margin-bottom: 12px; }}
        .empty-title {{ font-size: 15px; font-weight: 600; color: #374151; }}
        .empty-sub {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
        
        /* FOOTER */
        footer {{
            text-align: center;
            padding: 28px 24px;
            font-size: 11px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            margin-top: 48px;
        }}
        
        /* MOBILE */
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
            <div>
                <h1 class="site-title">OMRON News Intelligence</h1>
                <p class="site-subtitle">전자부품 영업팀을 위한 산업 뉴스 대시보드</p>
            </div>
        </div>
        <div class="stats-row">
            <div class="stat">
                <span class="stat-value">{total_articles}</span>
                <span class="stat-label">오늘의<br>기사</span>
            </div>
            <div class="stat">
                <span class="stat-value">{high_count}</span>
                <span class="stat-label">높은<br>중요도</span>
            </div>
            <div class="stat">
                <span class="stat-value">{len(CATEGORIES)}</span>
                <span class="stat-label">분석<br>카테고리</span>
            </div>
        </div>
        <p class="update-time">마지막 업데이트: {update_time}</p>
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
    Powered by Claude AI · 오므론전자부품 기술영업팀 전용 · 매일 오전 8시 자동 업데이트
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


def main():
    print("=" * 50)
    print("🏢 OMRON News Intelligence - 뉴스 수집 시작")
    print("=" * 50)

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    update_time = now.strftime("%Y년 %m월 %d일 %H:%M KST")
    print(f"⏰ 현재 시각: {update_time}\n")

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다!")
        print("   GitHub 저장소의 Settings > Secrets에 API 키를 추가하세요.")
        sys.exit(1)

    all_news = {}

    for i, cat in enumerate(CATEGORIES):
        print(f"\n[{i+1}/{len(CATEGORIES)}] {cat['icon']} {cat['label']} 수집 중...")
        articles = fetch_news_for_category(cat)
        all_news[cat["id"]] = articles

        # API 부하 방지를 위한 대기
        if i < len(CATEGORIES) - 1:
            import time
            time.sleep(3)

    # HTML 생성
    print("\n📄 HTML 파일 생성 중...")
    html = generate_html(all_news, update_time)

    # docs/index.html에 저장 (GitHub Pages용)
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "index.html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    total = sum(len(v) for v in all_news.values())
    print(f"\n✅ 완료! 총 {total}개 기사 수집")
    print(f"📁 파일 저장: {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
