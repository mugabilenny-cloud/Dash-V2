"""Mobile-first CSS. Keep all styling here."""
CSS = """
<style>
.block-container{padding:1rem 1rem 5rem;max-width:640px}
footer,#MainMenu{visibility:hidden}
.stButton>button,.stLinkButton>a,.stDownloadButton>button{width:100%;min-height:2.9rem;border-radius:12px;font-weight:600}
.stTabs [data-baseweb=tab-list]{gap:2px;overflow-x:auto}
.stTabs [data-baseweb=tab]{padding:.5rem .6rem;font-size:.9rem}
div[role=radiogroup][aria-orientation=horizontal],div[data-testid=stRadio] div[role=radiogroup]{flex-wrap:wrap;gap:.25rem .6rem}
.hero{border-radius:18px;padding:1.1rem 1.2rem;color:#fff;margin-bottom:.8rem}
.hero h1{margin:0;font-size:1.5rem;color:#fff}.hero p{margin:.2rem 0 0;opacity:.95}
.pill{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.75rem;font-weight:700}
.open{background:#D8F3DC;color:#1B4332}.closed{background:#FFE0E0;color:#7A1E1E}.neutral{background:#FFF3C4;color:#5C4A00}
.price{font-weight:700}
.step{padding:.35rem 0;font-size:1rem}.step.done{color:#1B7F3B}.step.now{font-weight:800}.step.todo{color:#999}
.fallback{font-size:.8rem;color:#666;border-top:1px solid #eee;margin-top:1.5rem;padding-top:.6rem}
</style>
"""


def hero(title: str, subtitle: str, color: str) -> str:
    return f'<div class="hero" style="background:{color}"><h1>{title}</h1><p>{subtitle}</p></div>'


def pill(text: str, state: bool | None) -> str:
    cls = "neutral" if state is None else ("open" if state else "closed")
    return f'<span class="pill {cls}">{text}</span>'
