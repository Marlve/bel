import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import chatMarkdown
import style


class ChatMarkdownTests(unittest.TestCase):
    def test_plain_text_is_untouched_besides_escaping(self):
        self.assertEqual(chatMarkdown.render("hello there"), "hello there")

    def test_html_in_the_reply_is_escaped_not_rendered(self):
        rendered = chatMarkdown.render("<script>alert(1)</script>")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_bold(self):
        self.assertEqual(chatMarkdown.render("**bold**"), "<b>bold</b>")

    def test_italic_star_and_underscore(self):
        self.assertEqual(chatMarkdown.render("*a*"), "<i>a</i>")
        self.assertEqual(chatMarkdown.render("_a_"), "<i>a</i>")

    def test_italic_does_not_trigger_inside_a_snake_case_identifier(self):
        self.assertEqual(chatMarkdown.render("my_var_name"), "my_var_name")

    def test_inline_code_uses_the_mono_font(self):
        rendered = chatMarkdown.render("`code`")
        self.assertIn(f'font-family:{style.CHAT_MONO_FAMILY}', rendered)
        self.assertIn("<code", rendered)
        self.assertIn(">code</code>", rendered)

    def test_fenced_code_block_is_a_distinct_block_with_line_breaks_kept(self):
        rendered = chatMarkdown.render("```\nline one\nline two\n```")
        self.assertIn("<pre", rendered)
        self.assertIn("line one\nline two", rendered)

    def test_bullet_list(self):
        rendered = chatMarkdown.render("- one\n- two")
        self.assertEqual(rendered, "<ul><li>one</li><li>two</li></ul>")

    def test_intro_line_directly_followed_by_a_list_has_no_blank_line(self):
        # The label renders this in a white-space:pre-wrap span, so a
        # literal "\n" next to a list would show as a real, unwanted blank
        # line stacked on top of <ul>'s own block margin.
        rendered = chatMarkdown.render("Steps:\n- one\n- two")
        self.assertEqual(rendered, "Steps:<ul><li>one</li><li>two</li></ul>")

    def test_list_directly_followed_by_a_trailing_line_has_no_blank_line(self):
        rendered = chatMarkdown.render("- one\n- two\nDone.")
        self.assertEqual(rendered, "<ul><li>one</li><li>two</li></ul>Done.")

    def test_numbered_list(self):
        rendered = chatMarkdown.render("1. one\n2. two")
        self.assertEqual(rendered, "<ol><li>one</li><li>two</li></ol>")

    def test_list_item_content_still_gets_inline_formatting(self):
        rendered = chatMarkdown.render("- **bold** item")
        self.assertEqual(rendered, "<ul><li><b>bold</b> item</li></ul>")

    def test_unclosed_bold_marker_shows_literally_instead_of_crashing(self):
        rendered = chatMarkdown.render("Hello **wor")
        self.assertEqual(rendered, "Hello **wor")

    def test_unclosed_bold_resolves_once_the_closing_marker_streams_in(self):
        partial = chatMarkdown.render("Hello **wor")
        complete = chatMarkdown.render("Hello **wor** ld")
        self.assertEqual(partial, "Hello **wor")
        self.assertEqual(complete, "Hello <b>wor</b> ld")

    def test_unclosed_inline_code_backtick_shows_literally(self):
        self.assertEqual(chatMarkdown.render("look at `foo"), "look at `foo")

    def test_unclosed_fence_shows_literally_until_closed(self):
        rendered = chatMarkdown.render("```\nline one")
        self.assertEqual(rendered, "```\nline one")

    def test_multiplication_asterisk_is_not_treated_as_italic(self):
        self.assertEqual(chatMarkdown.render("3 * 4 = 12"), "3 * 4 = 12")

    def test_bullet_directly_followed_by_numbered_list_stays_two_lists(self):
        rendered = chatMarkdown.render("- a\n1. b\n2. c")
        self.assertEqual(
            rendered, "<ul><li>a</li></ul><ol><li>b</li><li>c</li></ol>"
        )

    def test_numbered_directly_followed_by_bullet_stays_two_lists(self):
        rendered = chatMarkdown.render("1. a\n- b")
        self.assertEqual(rendered, "<ol><li>a</li></ol><ul><li>b</li></ul>")

    def test_single_hard_break_stays_a_literal_newline(self):
        # No blank source line between them - not a paragraph break.
        self.assertEqual(chatMarkdown.render("line one\nline two"), "line one\nline two")

    def test_blank_line_becomes_a_paragraph_break_not_a_double_newline(self):
        rendered = chatMarkdown.render("para one\n\npara two")
        self.assertNotIn("\n\n", rendered)
        self.assertIn("para one", rendered)
        self.assertIn(f'margin-top:{style.CHAT_PARAGRAPH_GAP}px', rendered)
        self.assertIn("para two", rendered)

    def test_multiple_blank_lines_still_produce_a_single_paragraph_gap(self):
        rendered = chatMarkdown.render("para one\n\n\n\npara two")
        self.assertEqual(rendered.count("margin-top"), 1)

    def test_paragraph_break_directly_after_a_list_still_gets_the_gap(self):
        rendered = chatMarkdown.render("- one\n- two\n\nDone.")
        self.assertEqual(
            rendered,
            f'<ul><li>one</li><li>two</li></ul><p style="margin:0;margin-top:{style.CHAT_PARAGRAPH_GAP}px;">Done.</p>',
        )

    def test_paragraph_gap_reflects_apply_scale_not_the_reference_value(self):
        # chatMarkdown used to `from style import CHAT_PARAGRAPH_GAP`, which
        # binds a copy at import time - apply_scale() (called once at real
        # startup, after this module is already imported) mutates style's
        # own attribute, but the frozen copy here never saw it, so a real
        # 4K/150% monitor would silently render the reference-scale gap
        # forever instead of the actual scaled one.
        try:
            style.apply_scale(1.5)
            rendered = chatMarkdown.render("para one\n\npara two")
            self.assertIn(f"margin-top:{style.CHAT_PARAGRAPH_GAP}px", rendered)
            self.assertNotEqual(style.CHAT_PARAGRAPH_GAP, 6)
        finally:
            importlib.reload(style)


if __name__ == "__main__":
    unittest.main()
