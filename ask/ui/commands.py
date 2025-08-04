from typing import Any
from ask.ui.components import Component, Box, Text, TextCallback
from ask.ui.styles import Colors, Styles, Theme

COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/exit': 'Exit the REPL',
    '/quit': 'Exit the REPL'}

class CommandsList(Box):
    leaf = True
    initial_state = {'selected_index': 0}

    def __init__(self, prefix: str = "", bash_mode: bool = False, handle_autocomplete: TextCallback | None = None) -> None:
        super().__init__(prefix=prefix, bash_mode=bash_mode, handle_autocomplete=handle_autocomplete)

    def handle_update(self, new_props: dict[str, Any]) -> None:
        matching_commands = self.get_matching_commands(new_props['prefix'])
        if self.state['selected_index'] >= len(matching_commands):
            self.state['selected_index'] = 0

    def handle_input(self, ch: str) -> None:
        matching_commands = self.get_matching_commands(self.props['prefix'])
        selected_index = self.state['selected_index']
        if not self.props['prefix'] or not matching_commands:
            return
        if ch.startswith('\x1b['):  # Arrow keys
            direction = ch[2:]
            if direction == 'A':  # Up arrow
                selected_index -= 1
            elif direction == 'B':  # Down arrow
                selected_index += 1
            self.state['selected_index'] = selected_index % len(matching_commands)
        elif ch == '\t' and self.props['handle_autocomplete'] and matching_commands:
            command = list(matching_commands.keys())[selected_index]
            self.props['handle_autocomplete'](command)

    def get_matching_commands(self, prefix: str) -> dict[str, str]:
        return {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(prefix)}

    def contents(self) -> list[Component]:
        matching_commands = self.get_matching_commands(self.props['prefix'])
        if not self.props['prefix'] or not matching_commands:
            bash_color = Theme.PINK if self.props['bash_mode'] else Theme.GRAY
            return [Text(Colors.hex('! for bash mode', bash_color) + Colors.hex(' · / for commands', Theme.GRAY), margin={'left': 2})]

        cmd_width = max(len(cmd) for cmd in matching_commands)
        result: list[Component] = []
        for idx, (cmd, desc) in enumerate(matching_commands.items()):
            if idx == self.state['selected_index']:  # add highlight
                cmd_text = Styles.bold(Colors.hex(cmd.ljust(cmd_width + 1), Theme.BLUE))
                desc_text = Colors.hex(desc, Theme.BLUE)
            else:
                cmd_text = Styles.bold(Colors.hex(cmd.ljust(cmd_width + 1), Theme.GRAY))
                desc_text = Colors.hex(desc, Theme.GRAY)
            result.append(Text(f"{cmd_text}  {desc_text}"))

        return result
