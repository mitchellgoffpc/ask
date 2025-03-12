from ask.ui.components import Component
from ask.ui.styles import Colors, Styles

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

    def __init__(self, prefix: str = ""):
        super().__init__(prefix=prefix)

    def render(self, _: list[str]) -> str:
        matching_commands = {cmd: desc for cmd, desc in COMMANDS.items() if cmd.startswith(self.props['prefix'])}
        if not self.props['prefix'] or not matching_commands:
            return ""
        cmd_width = max(len(cmd) for cmd in matching_commands)
        return "\n".join(
            f"{Styles.bold(Colors.hex(cmd, '#BE5103')).ljust(cmd_width + 11)}  {Colors.hex(desc, '#999999')}"
            for cmd, desc in matching_commands.items())
