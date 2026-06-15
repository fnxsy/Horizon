"""Beautiful self-contained HTML daily report with floating sidebar and collapsible categories."""

import re
from collections import OrderedDict
from typing import List

from ..models import ContentItem


_CJK = r"[一-鿿㐀-䶿]"
_ASCII = r"[A-Za-z0-9]"

CATEGORY_ORDER = ["AI/ML", "开源/编程", "系统/硬件", "安全/隐私", "时政/地缘", "科学/研究", "行业/商业", "其他"]
CATEGORY_ICONS = {
    "AI/ML": "🤖", "开源/编程": "💻", "系统/硬件": "⚙️",
    "安全/隐私": "🔒", "时政/地缘": "🌍", "科学/研究": "🔬",
    "行业/商业": "📊", "其他": "📋"
}


def _pangu(text: str) -> str:
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


def _score_color(score: float) -> str:
    if score >= 9: return "#e03131"
    if score >= 8: return "#f08c00"
    if score >= 7: return "#2f9e44"
    return "#868e96"


def _score_bg(score: float) -> str:
    if score >= 9: return "#fff5f5"
    if score >= 8: return "#fff9db"
    if score >= 7: return "#ebfbee"
    return "#f8f9fa"


def _score_emoji(score: float) -> str:
    if score >= 9: return "🔥"
    if score >= 8: return "⭐"
    if score >= 7: return "📌"
    return "📎"


def _group_items(items: List[ContentItem]) -> OrderedDict:
    groups = OrderedDict()
    for cat in CATEGORY_ORDER:
        groups[cat] = []
    for item in items:
        cat = item.metadata.get("category", "其他")
        if cat not in groups:
            cat = "其他"
        groups[cat].append(item)
    return OrderedDict((k, v) for k, v in groups.items() if v)


def _render_floating_toc(groups: OrderedDict, lang: str) -> str:
    rows = []
    idx = 0
    for cat, cat_items in groups.items():
        icon = CATEGORY_ICONS.get(cat, "📋")
        n = len(cat_items)
        rows.append(
            f'<div class="ftoc-cat" onclick="toggleCat(this)">'
            f'<span class="ftoc-cat-icon">{icon}</span>'
            f'<span class="ftoc-cat-name">{cat}</span>'
            f'<span class="ftoc-cat-n">{n}</span>'
            f'<svg class="ftoc-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>'
            f'</div>'
            f'<div class="ftoc-links">'
        )
        for item in cat_items:
            idx += 1
            title = str(item.metadata.get(f"title_{lang}") or item.title)
            title = title.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            if lang == "zh":
                title = _pangu(title)
            if len(title) > 24:
                title = title[:22] + "…"
            score = item.ai_score or 0
            sc = "s9" if score >= 9 else ("s8" if score >= 8 else "s7")
            rows.append(
                f'<a href="#item-{idx}" class="ftoc-link" data-idx="{idx}">'
                f'<span class="ftoc-dot {sc}"></span>'
                f'<span class="ftoc-text">{title}</span>'
                f'</a>'
            )
        rows.append('</div>')

    label = "目录" if lang == "zh" else "TOC"
    return f"""<aside class="floating-toc" id="toc">
    <div class="ftoc-header">
      <span class="ftoc-logo">🌅</span>
      <span class="ftoc-title">{label}</span>
      <button class="ftoc-close" onclick="toggleToc()" title="关闭">×</button>
    </div>
    <nav class="ftoc-nav">{"".join(rows)}</nav>
  </aside>
  <button class="toc-fab" id="tocFab" onclick="toggleToc()" title="目录">☰</button>"""


def _render_header(date: str, total: int, selected: int, groups: OrderedDict, lang: str) -> str:
    zh = lang == "zh"
    pills = "".join(
        f'<span class="hero-pill">{CATEGORY_ICONS.get(cat,"")} {cat} <strong>{len(items)}</strong></span>'
        for cat, items in groups.items()
    )
    return f"""
    <header class="hero">
      <div class="hero-badge">{date}</div>
      <h1>🌅 {'Horizon 每日速递' if zh else 'Horizon Daily'}</h1>
      <p class="hero-sub">{'从' if zh else 'From'} {total} {'条内容中精选' if zh else 'items'} {selected} {'条' if zh else 'selected'}</p>
      <div class="hero-pills">{pills}</div>
    </header>"""


def _render_item(item: ContentItem, lang: str, index: int) -> str:
    meta = item.metadata
    title = str(meta.get(f"title_{lang}") or item.title)
    title = title.replace("<", "&lt;").replace(">", "&gt;")
    url = str(item.url)
    score = item.ai_score or 0

    summary = (
        meta.get(f"detailed_summary_{lang}")
        or meta.get("detailed_summary")
        or item.ai_summary or ""
    )
    background = meta.get(f"background_{lang}") or meta.get("background") or ""
    discussion = meta.get(f"community_discussion_{lang}") or meta.get("community_discussion") or ""

    if lang == "zh":
        title = _pangu(title)
        summary = _pangu(summary)
        background = _pangu(background)
        discussion = _pangu(discussion)

    source_parts = []
    if meta.get("subreddit"): source_parts.append(f"r/{meta['subreddit']}")
    if meta.get("feed_name"): source_parts.append(meta["feed_name"])
    else: source_parts.append(item.author or item.source_type.value)
    if item.published_at:
        if lang == "zh":
            source_parts.append(f"{item.published_at.month}月{item.published_at.day}日 {item.published_at:%H:%M}")
        else:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
    source_line = " · ".join(source_parts)

    color = _score_color(score)
    bg = _score_bg(score)
    emoji = _score_emoji(score)

    L = {
        "bg": "背景" if lang == "zh" else "Background",
        "disc": "社区讨论" if lang == "zh" else "Discussion",
        "refs": "参考链接" if lang == "zh" else "References",
    }

    bg_html = f'<div class="bg-block"><span class="block-label">{L["bg"]}</span><p>{background}</p></div>' if background else ""
    disc_html = f'<div class="disc-block"><span class="block-label">💬 {L["disc"]}</span><p>{discussion}</p></div>' if discussion else ""

    sources = meta.get("sources") or []
    refs_html = ""
    if sources:
        links = "".join(f'<li><a href="{s["url"]}" target="_blank">{s["title"]}</a></li>' for s in sources[:5])
        refs_html = f'<details class="refs-details"><summary>{L["refs"]} ({len(sources)})</summary><ul class="refs-list">{links}</ul></details>'

    tags_html = ""
    if item.ai_tags:
        t = " ".join(f'<span class="tag">{t}</span>' for t in item.ai_tags[:6])
        tags_html = f'<div class="tags-row">{t}</div>'

    return f"""
  <article class="item-card" id="item-{index}">
    <div class="card-head">
      <div class="card-left">
        <span class="card-idx">{index}</span>
        <h2 class="card-title"><a href="{url}" target="_blank">{title}</a></h2>
      </div>
      <span class="card-score" style="background:{bg};color:{color}">{emoji} {score}/10</span>
    </div>
    <div class="card-body">
      <p class="card-summary">{summary}</p>
      <p class="card-source">{source_line}</p>
{bg_html}{disc_html}{refs_html}{tags_html}
    </div>
  </article>"""


CSS = r"""
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:24px}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:#f5f6fa;color:#2d3436;line-height:1.65;-webkit-font-smoothing:antialiased}

/* ── Hero ── */
.hero{background:linear-gradient(155deg,#0f0c29 0%,#1a1a3e 40%,#24243e 100%);color:#fff;padding:44px 32px 36px;text-align:center;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 80% 50% at 50% -20%,rgba(99,102,241,.25),transparent);pointer-events:none}
.hero-badge{display:inline-block;padding:4px 14px;border-radius:20px;background:rgba(255,255,255,.12);font-size:.78rem;letter-spacing:.06em;margin-bottom:12px;backdrop-filter:blur(4px)}
.hero h1{font-size:2rem;font-weight:800;letter-spacing:-.03em;margin-bottom:6px;position:relative}
.hero-sub{font-size:.9rem;opacity:.6;margin-bottom:20px;position:relative}
.hero-pills{display:flex;justify-content:center;flex-wrap:wrap;gap:8px;position:relative}
.hero-pill{display:inline-flex;align-items:center;gap:5px;padding:5px 14px;border-radius:20px;background:rgba(255,255,255,.08);font-size:.76rem;color:rgba(255,255,255,.75)}
.hero-pill strong{color:#fff;font-weight:700}

/* ── Content ── */
.container{max-width:820px;margin:0 auto;padding:0 20px 60px}

/* ── Category Sections ── */
.cat-section{margin-top:28px}
.cat-heading{display:flex;align-items:center;gap:10px;font-size:.95rem;font-weight:700;color:#636e72;margin-bottom:14px;padding:0 4px}
.cat-heading .cat-icon{font-size:1.1rem}
.cat-heading .cat-n{font-size:.76rem;color:#b2bec3;font-weight:500;margin-left:auto}

/* ── Cards ── */
.item-card{background:#fff;border-radius:16px;padding:22px 26px;margin-bottom:12px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 2px 8px rgba(0,0,0,.03);transition:box-shadow .2s,transform .15s;border:1px solid #f1f3f5}
.item-card:hover{box-shadow:0 4px 24px rgba(0,0,0,.07);transform:translateY(-1px);border-color:#e9ecef}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.card-left{display:flex;align-items:flex-start;gap:10px;flex:1}
.card-idx{display:flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:8px;background:#f1f3f5;color:#868e96;font-size:.72rem;font-weight:700;flex-shrink:0;margin-top:2px}
.card-title a{color:#1a1a2e;text-decoration:none;font-size:1.02rem;font-weight:700;line-height:1.45}
.card-title a:hover{color:#4c6ef5}
.card-score{font-size:.74rem;font-weight:700;padding:4px 12px;border-radius:20px;white-space:nowrap;flex-shrink:0}
.card-summary{font-size:.88rem;color:#495057;margin-bottom:8px;line-height:1.72}
.card-source{font-size:.74rem;color:#adb5bd}

.bg-block,.disc-block{margin-top:12px;padding:12px 16px;border-radius:10px;font-size:.83rem;line-height:1.65}
.bg-block{background:#f8f9fe;border-left:3px solid #748ffc}
.disc-block{background:#fef9e7;border-left:3px solid #fcc419}
.bg-block p,.disc-block p{margin-top:3px;color:#495057}
.block-label{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#adb5bd}

.refs-details{margin-top:12px;font-size:.8rem;color:#868e96}
.refs-details summary{cursor:pointer;font-weight:600;color:#495057}
.refs-list{margin-top:6px;padding-left:18px}
.refs-list li{margin-bottom:3px}
.refs-list a{color:#4c6ef5;text-decoration:none;font-size:.79rem}
.refs-list a:hover{text-decoration:underline}

.tags-row{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px}
.tag{display:inline-block;padding:3px 10px;background:#edf2ff;color:#4c6ef5;border-radius:20px;font-size:.72rem;font-weight:500}

/* ── Floating TOC (right side) ── */
.floating-toc{position:fixed;top:20px;right:20px;width:270px;max-height:calc(100vh - 40px);background:#fff;border-radius:16px;box-shadow:0 4px 32px rgba(0,0,0,.1),0 0 0 1px rgba(0,0,0,.04);z-index:100;display:flex;flex-direction:column;overflow:hidden;transition:transform .25s cubic-bezier(.4,0,.2,1),opacity .25s}
.floating-toc.hidden{transform:translateX(320px);opacity:0;pointer-events:none}
.ftoc-header{display:flex;align-items:center;gap:8px;padding:16px 16px 12px;border-bottom:1px solid #f1f3f5;flex-shrink:0}
.ftoc-logo{font-size:1.1rem}
.ftoc-title{font-size:.82rem;font-weight:700;color:#495057;flex:1}
.ftoc-close{width:26px;height:26px;border-radius:8px;border:none;background:#f1f3f5;color:#868e96;font-size:1rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s}
.ftoc-close:hover{background:#e9ecef}
.ftoc-nav{overflow-y:auto;padding:8px 12px 16px;flex:1}
.ftoc-nav::-webkit-scrollbar{width:3px}
.ftoc-nav::-webkit-scrollbar-thumb{background:#dee2e6;border-radius:4px}

/* Category header in floating TOC */
.ftoc-cat{display:flex;align-items:center;gap:8px;padding:10px 8px 6px;font-size:.76rem;font-weight:700;color:#636e72;cursor:pointer;user-select:none;border-radius:8px;transition:background .12s}
.ftoc-cat:hover{background:#f8f9fa}
.ftoc-cat-icon{font-size:.85rem}
.ftoc-cat-name{flex:1}
.ftoc-cat-n{font-size:.7rem;color:#adb5bd;font-weight:500}
.ftoc-chevron{transition:transform .2s;flex-shrink:0;color:#adb5bd}
.ftoc-cat.collapsed .ftoc-chevron{transform:rotate(-90deg)}
.ftoc-links{overflow:hidden;transition:max-height .3s ease}
.ftoc-cat.collapsed + .ftoc-links{max-height:0!important}

.ftoc-link{display:flex;align-items:center;gap:8px;padding:5px 8px 5px 20px;border-radius:6px;text-decoration:none;color:#636e72;font-size:.76rem;line-height:1.35;transition:background .12s}
.ftoc-link:hover{background:#f8f9fa}
.ftoc-link.active{background:#edf2ff;color:#4c6ef5}
.ftoc-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;background:#ced4da}
.ftoc-dot.s9{background:#e03131}
.ftoc-dot.s8{background:#f08c00}
.ftoc-dot.s7{background:#2f9e44}
.ftoc-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* TOC toggle FAB */
.toc-fab{display:none;position:fixed;bottom:24px;right:24px;width:48px;height:48px;border-radius:50%;background:#1a1a2e;color:#fff;border:none;font-size:1.2rem;cursor:pointer;z-index:200;box-shadow:0 4px 20px rgba(0,0,0,.25);transition:transform .15s,box-shadow .15s;align-items:center;justify-content:center}
.toc-fab:hover{transform:scale(1.05);box-shadow:0 6px 28px rgba(0,0,0,.3)}

.footer{text-align:center;padding:40px 16px;color:#b2bec3;font-size:.74rem}
.footer a{color:#868e96;text-decoration:none}
.footer a:hover{color:#636e72}

/* ── Responsive ── */
@media (max-width:1100px){
  .floating-toc{width:250px;right:10px;top:10px;max-height:calc(100vh - 20px)}
}
@media (max-width:900px){
  .floating-toc{display:none}
  .floating-toc.open-mobile{display:flex;position:fixed;top:10px;right:10px;bottom:10px;left:10px;width:auto;max-height:none;z-index:300;border-radius:16px}
  .toc-fab{display:flex}
  .container{padding:0 14px 60px}
  .hero{padding:36px 16px 28px}
  .hero h1{font-size:1.5rem}
  .item-card{padding:18px 16px}
}
@media (min-width:901px){
  .floating-toc{display:flex}
  .toc-fab{display:none}
}
"""

TEMPLATE = r"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Horizon Daily — {date}</title>
<style>{css}</style>
</head>
<body>
{toc}
<div class="container">
{header}
{items}
<footer class="footer">
  <p>Generated by <a href="https://github.com/jinghuazhao/Horizon" target="_blank">Horizon</a> · AI-Driven Information Aggregation · {date}</p>
</footer>
</div>
<script>
// Toggle floating panel visibility
var tocVisible = window.innerWidth > 900;
function updateTocVisibility() {{
  var toc = document.getElementById('toc');
  var fab = document.getElementById('tocFab');
  if (window.innerWidth > 900) {{
    toc.classList.remove('hidden','open-mobile');
    tocVisible = true;
    fab.style.display = 'none';
  }} else {{
    toc.classList.add('hidden');
    toc.classList.remove('open-mobile');
    tocVisible = false;
    fab.style.display = 'flex';
  }}
}}
window.addEventListener('resize', updateTocVisibility);

function toggleToc() {{
  var toc = document.getElementById('toc');
  if (window.innerWidth <= 900) {{
    toc.classList.toggle('open-mobile');
    toc.classList.remove('hidden');
  }} else {{
    tocVisible = !tocVisible;
    if (tocVisible) toc.classList.remove('hidden');
    else toc.classList.add('hidden');
  }}
}}

// Collapsible category drawers (collapsed by default)
function toggleCat(el) {{
  el.classList.toggle('collapsed');
  var links = el.nextElementSibling;
  if (!links || !links.classList.contains('ftoc-links')) return;
  if (el.classList.contains('collapsed')) {{
    links.style.maxHeight = '0px';
  }} else {{
    links.style.maxHeight = links.scrollHeight + 'px';
  }}
}}

// Initialize: collapse all, set heights
document.addEventListener('DOMContentLoaded', function() {{
  var cats = document.querySelectorAll('.ftoc-cat');
  cats.forEach(function(cat) {{
    cat.classList.add('collapsed');
    var links = cat.nextElementSibling;
    if (links && links.classList.contains('ftoc-links')) {{
      links.style.maxHeight = '0px';
      // Store natural height
      links._naturalHeight = links.scrollHeight;
    }}
  }});
  // First category expanded by default
  if (cats.length > 0) {{
    cats[0].classList.remove('collapsed');
    var firstLinks = cats[0].nextElementSibling;
    if (firstLinks && firstLinks.classList.contains('ftoc-links')) {{
      firstLinks.style.maxHeight = firstLinks.scrollHeight + 'px';
    }}
  }}
}});

// Scroll highlight
var links = document.querySelectorAll('.ftoc-link');
var cards = document.querySelectorAll('.item-card');
var activeCat = null;
var observer = new IntersectionObserver(function(entries) {{
  entries.forEach(function(e) {{
    var idx = e.target.id.replace('item-','');
    var link = document.querySelector('.ftoc-link[data-idx="'+idx+'"]');
    if (e.isIntersecting && link) {{
      links.forEach(function(l) {{ l.classList.remove('active'); }});
      link.classList.add('active');
      // Expand current category, collapse the previously expanded one
      var cat = link.closest('.ftoc-links');
      if (cat) {{
        var header = cat.previousElementSibling;
        if (header && header.classList.contains('ftoc-cat')) {{
          if (activeCat && activeCat !== header) {{
            activeCat.classList.add('collapsed');
            activeCat.nextElementSibling.style.maxHeight = '0px';
          }}
          if (header.classList.contains('collapsed')) {{
            header.classList.remove('collapsed');
            cat.style.maxHeight = cat.scrollHeight + 'px';
          }}
          activeCat = header;
        }}
      }}
    }}
  }});
}}, {{rootMargin: '-8% 0px -75% 0px'}});
cards.forEach(function(c) {{ observer.observe(c); }});
</script>
</body>
</html>"""


class HTMLRenderer:
    """Renders a beautiful self-contained HTML daily report with floating TOC and collapsible categories."""

    def render(
        self, items: List[ContentItem], date: str,
        total_fetched: int, language: str = "zh",
    ) -> str:
        lang = "zh" if language.startswith("zh") else "en"
        groups = _group_items(items)
        toc = _render_floating_toc(groups, lang) if items else ""
        header = _render_header(date, total_fetched, len(items), groups, lang)

        sections = []
        idx = 0
        for cat, cat_items in groups.items():
            icon = CATEGORY_ICONS.get(cat, "📋")
            cards_html = []
            for item in cat_items:
                idx += 1
                cards_html.append(_render_item(item, lang, idx))
            sections.append(
                f'<section class="cat-section">'
                f'<div class="cat-heading"><span class="cat-icon">{icon}</span>{cat}<span class="cat-n">{len(cat_items)} 条</span></div>'
                f'{"".join(cards_html)}'
                f'</section>'
            )
        items_html = "\n".join(sections) if items else '<p style="text-align:center;color:#b2bec3;padding:60px 0">今日暂无重要动态</p>'

        return TEMPLATE.format(
            lang_code=lang, date=date, css=CSS,
            toc=toc, header=header, items=items_html,
        )
