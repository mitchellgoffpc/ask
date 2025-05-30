import unittest
from unittest.mock import patch
from ask.ui.styles import ansi_strip
from ask.ui.messages import Prompt, TextResponse, ToolResponse


class TestPrompt(unittest.TestCase):
    def test_prompt_basic_rendering(self):
        """Test Prompt renders correctly with basic text."""
        prompt = Prompt("What would you like to do?")
        rendered = ansi_strip(prompt.render([]))
        self.assertEqual(rendered, "> What would you like to do?\n")


class TestTextResponse(unittest.TestCase):
    def test_text_response_basic_rendering(self):
        """Test TextResponse renders correctly with basic text."""
        text_response = TextResponse("This is a response message")
        rendered = ansi_strip(text_response.render([]))

        expected = "⏺ This is a response message\n"
        self.assertEqual(rendered, expected)

    def test_text_response_multiline_text(self):
        """Test TextResponse renders correctly with multiline text."""
        text_response = TextResponse("Line 1\nLine 2\nLine 3")
        rendered = ansi_strip(text_response.render([]))

        expected = "⏺ Line 1\n  Line 2\n  Line 3\n"
        self.assertEqual(rendered, expected)

    @patch('ask.ui.components.terminal_width', 30)
    def test_text_response_long_text(self):
        """Test TextResponse renders correctly with long text that wraps."""
        long_text = "This is a very long response message that should wrap to multiple lines when rendered."
        text_response = TextResponse(long_text)
        rendered = ansi_strip(text_response.render([]))

        expected_lines = [
            "⏺ This is a very long response",
            "   message that should wrap to",
            "   multiple lines when rendere",
            "  d."
        ]
        expected = "\n".join(expected_lines) + "\n"
        self.assertEqual(rendered, expected)


class TestToolResponse(unittest.TestCase):
    def test_tool_response_basic_rendering(self):
        """Test ToolResponse renders correctly with single argument and result."""
        tool_response = ToolResponse(tool="Read", args=["test/ui/test_box.py"], result=["Read 149 lines"])
        rendered = ansi_strip(tool_response.render([]))

        expected = "⏺ Read(test/ui/test_box.py)…\n⎿  Read 149 lines\n"
        self.assertEqual(rendered, expected)

    def test_tool_response_multiple_args_and_results(self):
        """Test ToolResponse renders correctly with multiple arguments and result lines."""
        tool_response = ToolResponse(
            tool="Grep",
            args=["pattern", "*.py"],
            result=["Found 3 matches", "file1.py:10:match", "file2.py:25:match"]
        )
        rendered = ansi_strip(tool_response.render([]))

        expected = "⏺ Grep(pattern, *.py)…\n⎿  Found 3 matches\n⎿  file1.py:10:match\n⎿  file2.py:25:match\n"
        self.assertEqual(rendered, expected)

    def test_tool_response_empty_cases(self):
        """Test ToolResponse renders correctly with empty arguments and results."""
        # Empty args
        tool_response = ToolResponse(tool="Status", args=[], result=["System OK"])
        rendered = ansi_strip(tool_response.render([]))
        expected = "⏺ Status…\n⎿  System OK\n"
        self.assertEqual(rendered, expected)

        # Empty result
        tool_response = ToolResponse(tool="Bash", args=["ls"], result=[])
        rendered = ansi_strip(tool_response.render([]))
        expected = "⏺ Bash(ls)…\n"
        self.assertEqual(rendered, expected)
