"""Source-preserving boundary between Markdown text and the Qt editor.

This adapter deliberately uses QTextEdit's plain-text API. It does not render
Markdown or convert source into rich text. Keeping this boundary explicit lets
a future editor implementation replace the adapter without changing storage
call sites.
"""


class PlainTextMarkdownAdapter:
    """Read and write the editor as an unchanged Markdown source string.

    In this implementation, source and document text have a one-to-one
    positional relationship: no Markdown tokens are hidden or inserted.
    QTextCursor positions are passed through unchanged. A future live-preview
    implementation must replace these identity mappings with mappings that
    account for rendered and hidden Markdown syntax.
    """

    def __init__(self, text_edit):
        self._text_edit = text_edit

    def read_source(self):
        """Return the exact plain-text content currently held by the editor."""
        return self._text_edit.toPlainText()

    def load_source(self, source):
        """Load Markdown source without interpreting or formatting it."""
        self._text_edit.setPlainText(source)

    @staticmethod
    def source_to_editor_position(position):
        """Map a source offset to a Qt document position in plain-text mode."""
        return position

    @staticmethod
    def editor_to_source_position(position):
        """Map a Qt document position to a source offset in plain-text mode."""
        return position
