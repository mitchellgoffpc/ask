import unittest
from ask.ui.commands import CommandsList, COMMANDS
from ask.ui.styles import ansi_strip


class TestCommandsListCreation(unittest.TestCase):
    def test_commands_list_creation(self):
        """Test CommandsList component creation with various props."""
        # Basic creation
        commands_list = CommandsList()
        self.assertEqual(commands_list.props['prefix'], "")
        self.assertFalse(commands_list.props['bash_mode'])
        self.assertTrue(commands_list.leaf)
        self.assertEqual(commands_list.state['selected_index'], 0)

        # With custom props
        commands_list = CommandsList(prefix="/h", bash_mode=True)
        self.assertEqual(commands_list.props['prefix'], "/h")
        self.assertTrue(commands_list.props['bash_mode'])

    def test_get_matching_commands(self):
        """Test get_matching_commands method with various prefixes."""
        commands_list = CommandsList()

        # Empty prefix should return all commands
        matching = commands_list.get_matching_commands("")
        self.assertEqual(matching, COMMANDS)

        # Specific prefix should return matching commands only
        matching = commands_list.get_matching_commands("/h")
        expected = {'/help': 'Show help and available commands'}
        self.assertEqual(matching, expected)

        # Prefix with multiple matches
        matching = commands_list.get_matching_commands("/c")
        expected = {
            '/clear': 'Clear conversation history and free up context',
            '/compact': 'Clear conversation history but keep a summary in context',
            '/config': 'Open config panel',
            '/cost': 'Show the total cost and duration of the current session'
        }
        self.assertEqual(matching, expected)

        # Non-matching prefix should return empty dict
        matching = commands_list.get_matching_commands("/xyz")
        self.assertEqual(matching, {})

    def test_partial_command_matching(self):
        """Test that partial commands match correctly."""
        commands_list = CommandsList()

        # Single character should match multiple commands
        matching = commands_list.get_matching_commands("/")
        self.assertEqual(len(matching), len(COMMANDS))

        # Test edge cases
        matching = commands_list.get_matching_commands("/q")
        expected = {'/quit': 'Exit the REPL'}
        self.assertEqual(matching, expected)


class TestCommandsListInputHandling(unittest.TestCase):
    def test_arrow_key_navigation(self):
        """Test arrow key navigation through commands."""
        commands_list = CommandsList(prefix="/c")
        matching_commands = commands_list.get_matching_commands("/c")
        num_commands = len(matching_commands)

        # Start at index 0
        self.assertEqual(commands_list.state['selected_index'], 0)

        # Down arrow should move to next command
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], 1)

        # Another down arrow
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], 2)

        # Up arrow should move back
        commands_list.handle_input('\x1b[A')
        self.assertEqual(commands_list.state['selected_index'], 1)

        # Wrap around at end - move to last command then down should wrap to 0
        commands_list.state['selected_index'] = num_commands - 1
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], 0)

        # Wrap around at beginning - move to first command then up should wrap to last
        commands_list.state['selected_index'] = 0
        commands_list.handle_input('\x1b[A')
        self.assertEqual(commands_list.state['selected_index'], num_commands - 1)

    def test_arrow_key_edge_cases(self):
        """Test arrow key navigation on edge cases."""
        # No prefix
        commands_list = CommandsList(prefix="")
        initial_index = commands_list.state['selected_index']
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], initial_index)

        # No matching commands
        commands_list = CommandsList(prefix="/xyz")
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], initial_index)

        # Single command
        commands_list = CommandsList(prefix="/help")
        commands_list.handle_input('\x1b[B')
        self.assertEqual(commands_list.state['selected_index'], initial_index)
        commands_list.handle_input('\x1b[A')
        self.assertEqual(commands_list.state['selected_index'], initial_index)


class TestCommandsListUpdateHandling(unittest.TestCase):
    def test_handle_update_resets_selection(self):
        """Test that handle_update resets selected_index when it's out of bounds."""
        commands_list = CommandsList(prefix="/c")
        commands_list.state['selected_index'] = 3
        commands_list.handle_update({'prefix': '/help'})

        # selected_index should be reset to 0 since 3 >= 1
        self.assertEqual(commands_list.state['selected_index'], 0)

    def test_handle_update_with_empty_results(self):
        """Test handle_update when new prefix has no matches."""
        commands_list = CommandsList(prefix="/c")
        commands_list.state['selected_index'] = 2
        commands_list.handle_update({'prefix': '/xyz'})

        # Should reset to 0 since no matching commands
        self.assertEqual(commands_list.state['selected_index'], 0)


class TestCommandsListRendering(unittest.TestCase):
    def test_render_help_text_modes(self):
        """Test rendering help text in both normal and bash modes."""
        for bash_mode in (False, True):
            with self.subTest(bash_mode=bash_mode):
                commands_list = CommandsList(prefix="", bash_mode=bash_mode)
                contents = commands_list.contents()
                self.assertEqual(len(contents), 1)
                text_content = ansi_strip(contents[0].render([]))
                self.assertIn("! for bash mode", text_content)
                self.assertIn("/ for commands", text_content)

    def test_render_single_command(self):
        """Test rendering when only one command matches."""
        commands_list = CommandsList(prefix="/help")
        contents = commands_list.contents()

        self.assertEqual(len(contents), 1)
        text_content = ansi_strip(contents[0].render([]))
        self.assertIn("/help", text_content)
        self.assertIn("Show help and available commands", text_content)

    def test_render_multiple_commands(self):
        """Test rendering multiple commands with a common prefix."""
        commands_list = CommandsList(prefix="/c")
        contents = commands_list.contents()
        matching_commands = commands_list.get_matching_commands("/c")
        self.assertEqual(len(contents), len(matching_commands))

        # Verify the commands and descriptions is present in the rendered output
        for content, (cmd, desc) in zip(contents, matching_commands.items(), strict=True):
            text = ansi_strip(content.render([]))
            self.assertIn(cmd, text)
            self.assertIn(desc, text)

    def test_render_selection_changes(self):
        """Test that different selections produce different output."""
        commands_list = CommandsList(prefix="/c")
        commands_list.state['selected_index'] = 0
        contents_0 = commands_list.render([content.render([]) for content in commands_list.contents()])
        commands_list.state['selected_index'] = 1
        contents_1 = commands_list.render([content.render([]) for content in commands_list.contents()])

        # The rendered output should be different due to highlighting
        self.assertNotEqual(contents_0, contents_1)
