"""Tests for structured_text utilities."""

from __future__ import annotations

from agentforge.utils import structured_text as st


def test_split_paragraphs() -> None:
    text = "a\n\nb\n\n\nc"
    assert st.split_paragraphs(text) == ["a", "b", "c"]


def test_extract_fenced_code_blocks() -> None:
    src = """Intro\n```python\nx = 1\n```\nout\n```\nplain\n```"""
    blocks = st.extract_fenced_code_blocks(src)
    assert len(blocks) >= 2
    assert blocks[0].language == "python"
    assert "x = 1" in blocks[0].body


def test_extract_headings_and_outline() -> None:
    md = "# T\n\n## A\n\n### B\n"
    hs = st.extract_markdown_headings(md)
    assert len(hs) == 3
    tree = st.build_heading_outline(hs)
    assert len(tree) == 1
    assert tree[0].children


def test_extract_links() -> None:
    md = "See [x](https://a.com) and [y](http://b)"
    ls = st.extract_markdown_links(md)
    assert len(ls) == 2


def test_text_stats() -> None:
    md = "# H\n\n[x](u)\n\n```\nc\n```\n"
    stats = st.text_stats(md)
    assert stats["heading_count"] >= 1
    assert stats["link_count"] >= 1


def test_count_words_and_reading() -> None:
    assert st.count_words("one two three") == 3
    assert st.estimate_reading_minutes("word " * 500) > 0


def test_bullets_and_numbered() -> None:
    t = "- a\n* b\n+ c\n1. first\n2) second"
    assert len(st.extract_bullet_lines(t)) == 3
    assert st.extract_numbered_items(t) == ["first", "second"]


def test_strip_inline_md() -> None:
    s = st.strip_markdown_inline("**b** and `c`")
    assert "b" in s and "c" in s


def test_slugify_title() -> None:
    assert "hello" in st.slugify_title("Hello World!!!")


def test_truncate_with_ellipsis() -> None:
    assert len(st.truncate_with_ellipsis("abcdef", 4)) <= 4


def test_find_line_ranges() -> None:
    t = "l1\nl2\nneedle\nl4"
    r = st.find_line_ranges_for_substrings(t, "needle")
    assert r == [(3, 3)]


def test_windowed_and_batches_import() -> None:
    from agentforge.utils.iterextras import batches, windowed

    assert list(batches(range(5), 2)) == [[0, 1], [2, 3], [4]]
    assert list(windowed([1, 2, 3, 4], 2)) == [(1, 2), (2, 3), (3, 4)]

