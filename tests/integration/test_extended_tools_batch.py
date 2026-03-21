"""Integration tests for newly added tools (template, csv, xml, encoding, uuid, chrono, json schema)."""

from __future__ import annotations

import json

import pytest

from agentforge.tools.chrono_tool import ChronoTool
from agentforge.tools.csv_tool import CsvTool
from agentforge.tools.encoding_tool import EncodingTool
from agentforge.tools.json_schema_tool import JsonSchemaTool
from agentforge.tools.template_tool import TemplateTool
from agentforge.tools.uuid_tool import UuidTool
from agentforge.tools.xml_tool import XmlTool
from agentforge.tools.text_structure_tool import TextStructureTool


@pytest.mark.asyncio
async def test_template_render_and_validate() -> None:
    t = TemplateTool()
    r = await t.execute(action="validate_syntax", template_text="Hello {{ name }}")
    assert r.success
    r2 = await t.execute(
        action="render",
        template_text="Hi {{ name }}!",
        context_json=json.dumps({"name": "Ada"}),
    )
    assert r2.success
    assert "Ada" in r2.output


@pytest.mark.asyncio
async def test_csv_parse_and_stats() -> None:
    t = CsvTool()
    text = "name,score\na,1\nb,2\n"
    r = await t.execute(action="parse", text=text, has_header=True, max_rows=10)
    assert r.success
    assert "a" in r.output
    r2 = await t.execute(action="stats", text=text, has_header=True)
    assert r2.success
    assert "row_count" in r2.output


@pytest.mark.asyncio
async def test_csv_select_columns() -> None:
    t = CsvTool()
    text = "a,b,c\n1,2,3\n4,5,6\n"
    r = await t.execute(
        action="select_columns",
        text=text,
        has_header=True,
        columns=["a", "c"],
    )
    assert r.success
    data = json.loads(r.output)
    assert data[0] == {"a": "1", "c": "3"}


@pytest.mark.asyncio
async def test_xml_parse_summary_and_path() -> None:
    t = XmlTool()
    xml = '<?xml version="1.0"?><root><item id="1">hello</item></root>'
    r = await t.execute(action="parse_summary", xml_text=xml)
    assert r.success
    r2 = await t.execute(action="path", xml_text=xml, path="/root/item")
    assert r2.success
    assert "hello" in r2.output


@pytest.mark.asyncio
async def test_encoding_roundtrip() -> None:
    t = EncodingTool()
    r = await t.execute(action="base64_encode", text="hi")
    assert r.success
    r2 = await t.execute(action="base64_decode", text=r.output.strip())
    assert r2.success
    assert r2.output == "hi"


@pytest.mark.asyncio
async def test_uuid_v4_and_validate() -> None:
    t = UuidTool()
    r = await t.execute(action="uuid4", count=1)
    assert r.success
    val = r.output.strip()
    r2 = await t.execute(action="validate", value=val)
    assert r2.success


@pytest.mark.asyncio
async def test_chrono_relative() -> None:
    t = ChronoTool()
    r = await t.execute(action="relative", phrase="in 1 hour")
    assert r.success
    assert "resolved_iso" in r.output


@pytest.mark.asyncio
async def test_json_schema_validate_ok() -> None:
    t = JsonSchemaTool()
    data = json.dumps({"name": "x", "age": 30})
    schema = json.dumps(
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
            },
            "required": ["name", "age"],
        }
    )
    r = await t.execute(data_json=data, schema_json=schema)
    assert r.success


@pytest.mark.asyncio
async def test_json_schema_validate_fail() -> None:
    t = JsonSchemaTool()
    data = json.dumps({"name": "x"})
    schema = json.dumps(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
    )
    r = await t.execute(data_json=data, schema_json=schema)
    assert not r.success


@pytest.mark.asyncio
async def test_uuid7_unavailable_graceful() -> None:
    import uuid as uuid_mod

    t = UuidTool()
    if getattr(uuid_mod, "uuid7", None) is None:
        r = await t.execute(action="uuid7")
        assert not r.success
    else:
        r = await t.execute(action="uuid7")
        assert r.success


@pytest.mark.asyncio
async def test_chrono_merge_intervals() -> None:
    t = ChronoTool()
    payload = json.dumps(
        [
            ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
            ["2024-01-01T12:00:00Z", "2024-01-03T00:00:00Z"],
        ]
    )
    r = await t.execute(action="merge_intervals", intervals_json=payload)
    assert r.success


@pytest.mark.asyncio
async def test_xml_findall() -> None:
    t = XmlTool()
    xml = "<r><item>a</item><item>b</item></r>"
    r = await t.execute(action="findall", xml_text=xml, tag_name="item")
    assert r.success
    assert "count" in r.output


@pytest.mark.asyncio
async def test_text_structure_stats() -> None:
    t = TextStructureTool()
    doc = "# Title\n\n[link](https://x)\n\n```py\n1\n```\n"
    r = await t.execute(action="stats", text=doc)
    assert r.success
    assert "word_count" in r.output


@pytest.mark.asyncio
async def test_encoding_hex() -> None:
    t = EncodingTool()
    r = await t.execute(action="hex_encode", text="ab")
    assert r.success
    r2 = await t.execute(action="hex_decode", text=r.output)
    assert r2.success
    assert r2.output == "ab"
