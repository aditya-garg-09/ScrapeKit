"""Streamlit UI for ScrapeKit.

A local, user-friendly interface to scrape public web pages safely,
inspect structured extraction results, and download JSON and Markdown outputs.
"""

import json
from pathlib import Path

import streamlit as st

from app.exporter import export_json, export_markdown, render_markdown
from app.fetcher import ContentTypeError, FetchError, RedirectError, ResponseSizeError, fetch
from app.models import ContentInfo, PageInfo, ScrapeResult, SourceInfo, StatsInfo
from app.parser import parse_html
from app.robots import RobotsChecker, RobotsError
from app.security import SecurityError

OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="ScrapeKit — Web Scraper",
    page_icon="🕸️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #6c757d;
        margin-bottom: 1.5rem;
    }
    .badge-allowed {
        background-color: #d1e7dd;
        color: #0f5132;
        padding: 0.25rem 0.6rem;
        border-radius: 0.375rem;
        font-weight: 600;
    }
    .badge-blocked {
        background-color: #f8d7da;
        color: #842029;
        padding: 0.25rem 0.6rem;
        border-radius: 0.375rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🕸️ ScrapeKit</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Local-first, security-conscious HTML scraper with SSRF protection and robots.txt compliance.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Options")
    check_robots = st.checkbox("Respect robots.txt", value=True, help="Disables scraping if forbidden by the site's robots.txt")
    save_to_disk = st.checkbox("Save outputs to outputs/", value=True, help="Save .json and .md files to local outputs directory")
    
    st.markdown("---")
    st.markdown("### 🛡️ Security Guarantees")
    st.markdown(
        "- **SSRF Guard**: Blocks local, private, link-local, and reserved IP ranges.\n"
        "- **Redirect Inspector**: Validates every redirect target hop.\n"
        "- **Resource Limits**: 5 MB max response size, 20s read timeout.\n"
        "- **Format Safety**: Restricts fetches strictly to HTML."
    )

col_input, col_btn = st.columns([5, 1])
with col_input:
    target_url = st.text_input(
        "Target URL",
        placeholder="https://example.com",
        label_visibility="collapsed",
    )
with col_btn:
    scrape_clicked = st.button("🚀 Scrape", type="primary", use_container_width=True)

if scrape_clicked:
    if not target_url or not target_url.strip():
        st.warning("Please provide a valid URL to scrape.")
    else:
        url = target_url.strip()
        with st.spinner(f"Validating and fetching {url}..."):
            try:
                robots_checker = RobotsChecker()
                fetch_result = fetch(url, robots_checker=robots_checker, check_robots=check_robots)

                parsed = parse_html(fetch_result.html, base_url=fetch_result.final_url)

                result = ScrapeResult(
                    source=SourceInfo(
                        requested_url=fetch_result.requested_url,
                        final_url=fetch_result.final_url,
                        status_code=fetch_result.status_code,
                        content_type=fetch_result.content_type,
                        robots_checked=fetch_result.robots_checked,
                        robots_allowed=fetch_result.robots_allowed,
                        robots_url=fetch_result.robots_url,
                    ),
                    page=PageInfo(
                        title=parsed.title,
                        description=parsed.description,
                        canonical_url=parsed.canonical_url,
                    ),
                    content=ContentInfo(
                        headings=parsed.headings,
                        links=parsed.links,
                        text=parsed.text,
                    ),
                    stats=StatsInfo(
                        word_count=parsed.stats.get("word_count", 0),
                        character_count=parsed.stats.get("character_count", 0),
                        heading_count=parsed.stats.get("heading_count", 0),
                        link_count=parsed.stats.get("link_count", 0),
                    ),
                )

                json_path = None
                md_path = None
                if save_to_disk:
                    json_path = export_json(result, OUTPUTS_DIR)
                    md_path = export_markdown(result, OUTPUTS_DIR)

                st.session_state["last_result"] = result
                st.session_state["json_path"] = json_path
                st.session_state["md_path"] = md_path

                st.success("✅ Scrape completed successfully!")

            except SecurityError as exc:
                st.error(f"🛡️ **Scrape Blocked (Security / SSRF)**: {exc}")
            except RobotsError as exc:
                st.error(f"🤖 **Scrape Blocked (robots.txt)**: {exc}")
            except ContentTypeError as exc:
                st.error(f"📄 **Scrape Failed (Content-Type)**: {exc}")
            except ResponseSizeError as exc:
                st.error(f"⚠️ **Scrape Failed (Size Limit)**: {exc}")
            except RedirectError as exc:
                st.error(f"🔄 **Scrape Failed (Redirect Issue)**: {exc}")
            except FetchError as exc:
                st.error(f"🌐 **Scrape Failed (HTTP/Network)**: {exc}")
            except Exception as exc:
                st.error(f"❌ **Unexpected Error**: {exc}")

if "last_result" in st.session_state:
    res: ScrapeResult = st.session_state["last_result"]

    st.markdown("---")
    
    # Overview cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Words", res.stats.word_count)
    c2.metric("Characters", res.stats.character_count)
    c3.metric("Headings", res.stats.heading_count)
    c4.metric("Links", res.stats.link_count)

    st.subheader(res.page.title or "Untitled Page")
    
    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        st.markdown(f"**Requested URL**: [{res.source.requested_url}]({res.source.requested_url})")
        st.markdown(f"**Final URL**: [{res.source.final_url}]({res.source.final_url})")
        if res.page.canonical_url:
            st.markdown(f"**Canonical**: [{res.page.canonical_url}]({res.page.canonical_url})")
    with col_meta2:
        st.markdown(f"**Status Code**: `{res.source.status_code}` ({res.source.content_type})")
        robots_badge = "Allowed" if res.source.robots_allowed else "Blocked"
        st.markdown(f"**robots.txt**: `{robots_badge}`")
        if res.page.description:
            st.markdown(f"**Description**: *{res.page.description}*")

    st.markdown("---")

    # Tabs for structured data
    tab_text, tab_headings, tab_links, tab_json = st.tabs(["📝 Text Content", "📌 Headings", "🔗 Links", "📦 Raw JSON"])

    with tab_text:
        st.text_area("Extracted & Cleaned Text", res.content.text, height=350)

    with tab_headings:
        if res.content.headings:
            for h in res.content.headings:
                lvl = h.get("level", 1)
                text = h.get("text", "")
                st.markdown(f"{'#' * lvl} {text}")
        else:
            st.info("No headings found on this page.")

    with tab_links:
        if res.content.links:
            st.dataframe(res.content.links, use_container_width=True)
        else:
            st.info("No links found on this page.")

    with tab_json:
        st.json(res.to_dict())

    # Download buttons
    st.markdown("---")
    down_col1, down_col2, down_col3 = st.columns([1, 1, 3])
    with down_col1:
        st.download_button(
            label="⬇️ Download JSON",
            data=json.dumps(res.to_dict(), indent=2, ensure_ascii=False),
            file_name=f"{res.source.final_url.split('//')[-1].replace('/', '-')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with down_col2:
        st.download_button(
            label="⬇️ Download Markdown",
            data=render_markdown(res),
            file_name=f"{res.source.final_url.split('//')[-1].replace('/', '-')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with down_col3:
        if st.session_state.get("json_path"):
            st.caption(f"Saved locally to `{st.session_state['json_path']}` and `{st.session_state['md_path']}`")
