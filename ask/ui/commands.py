from ask.ui.components import Component, Text
from ask.ui.styles import Colors, Styles, Theme

COMMANDS = {
    '/clear': 'Clear conversation history and free up context',
    '/compact': 'Clear conversation history but keep a summary in context',
    '/config': 'Open config panel',
    '/cost': 'Show the total cost and duration of the current session',
    '/exit': 'Exit the REPL',
    '/help': 'Show help and available commands',
    '/init': 'Initialize a new MEMORY.md file with codebase documentation',
    '/quit': 'Exit the REPL'}

class CommandsList(Component):
    leaf = True

    def __init__(self, prefix: str = "", bash_mode: bool = False):
        super().__init__(prefix=prefix, bash_mode=bash_mode)

    def contents(self) -> list[Component]:
        matching_commands = {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(self.props['prefix'])}
        if not self.props['prefix'] or not matching_commands:
            bash_color = Theme.PINK if self.props['bash_mode'] else Theme.GRAY
            return [Text(Colors.hex('! for bash mode', bash_color) + Colors.hex(' · / for commands', Theme.GRAY), margin={'left': 2})]
        cmd_width = max(len(cmd) for cmd in matching_commands)
        return [
            Text(f"{Styles.bold(Colors.hex(cmd.ljust(cmd_width + 1), Theme.ORANGE))}  {Colors.hex(desc, Theme.GRAY)}")
            for cmd, desc in matching_commands.items()
        ]
