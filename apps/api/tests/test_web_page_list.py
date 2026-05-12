from app.services.crawler import extract_page_links


def test_extract_page_links_filters_prefixes() -> None:
    html = '<a href="/about">about</a><a href="/blog/ai-chips">post</a>'
    links = extract_page_links(
        html,
        "https://epoch.ai/latest",
        ["/blog/"],
        10,
    )
    assert links == ["https://epoch.ai/blog/ai-chips"]


def test_extract_page_links_uses_base_domain() -> None:
    html = '<a href="/engineering/managed-agents">post</a><a href="https://other.com/engineering/bad">bad</a>'
    links = extract_page_links(
        html,
        "https://www.anthropic.com/engineering",
        ["/engineering/"],
        10,
    )
    assert links == ["https://www.anthropic.com/engineering/managed-agents"]
