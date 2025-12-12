from typing import Any

from ask.ui.core.components import Component, Text
from ask.ui.core.styles import Colors, Styles, Theme

def ToDos(todos: dict[str, Any], expanded: bool) -> Component:
    if expanded:
        lines = []
        for item in todos['todos']:
            if item['status'] == 'pending':
                lines.append(f"☐ {item['content']}")
            elif item['status'] == "in_progress":
                lines.append(f"☐ {Styles.bold(item['content'])}")
            elif item['status'] == "completed":
                lines.append(f"☒ {Colors.hex(Styles.strikethrough(item['content']), Theme.GRAY)}")
        return Text("\n".join(lines))
    else:
        for item in todos['todos']:
            if item['status'] in ['pending', 'in_progress']:
                return Text(Colors.hex(f"Next: {item['content']}", Theme.GRAY))
        return Text(Colors.hex('Finished', Theme.GRAY))
