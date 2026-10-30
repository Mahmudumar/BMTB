"""Tests for the source-preserving Markdown editor boundary."""

from scripts.markdown_editor import PlainTextMarkdownAdapter


class FakeTextEdit:
    def __init__(self):
        self.text = ""

    def toPlainText(self):
        return self.text

    def setPlainText(self, text):
        self.text = text


def test_adapter_preserves_markdown_source_verbatim():
    editor = FakeTextEdit()
    adapter = PlainTextMarkdownAdapter(editor)
    source = "# Heading\n\n**goat** and _italic_\n"

    adapter.load_source(source)

    assert adapter.read_source() == source
    assert editor.text == source


def test_adapter_preserves_empty_source():
    editor = FakeTextEdit()
    adapter = PlainTextMarkdownAdapter(editor)

    adapter.load_source("")

    assert adapter.read_source() == ""


def test_position_mapping_is_identity_in_plain_text_mode():
    positions = (0, 1, 7, 42)

    for position in positions:
        assert PlainTextMarkdownAdapter.source_to_editor_position(position) == position
        assert PlainTextMarkdownAdapter.editor_to_source_position(position) == position


def test_adapter_preserves_leading_and_trailing_whitespace():
    editor = FakeTextEdit()
    adapter = PlainTextMarkdownAdapter(editor)
    source = "  **goat**  \\n"

    adapter.load_source(source)

    assert adapter.read_source() == source
