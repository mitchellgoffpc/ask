from ask.ui.core import UI, Axis, Colors
from ask.ui.theme import Theme


def Diff(diff: list[str], rejected: bool = False) -> UI.Component:
    components: list[UI.Component] = []
    old_line_num, new_line_num = 1, 1
    for line in diff[2:]:  # Skip header lines
        delta = line[1:].rstrip('\n')
        if line.startswith('@@'):
            parts = line.rstrip('\n').split()
            if len(parts) >= 2:
                old_range = parts[1][1:].split(',')
                new_range = parts[2][1:].split(',')
                old_line_num = int(old_range[0])
                new_line_num = int(new_range[0])
            if components:
                components.append(UI.Text(" ... "))
        elif line.startswith('-'):
            line_num = f"{old_line_num:>4}"
            fg_color = Theme.FADED_RED if rejected else Theme.RED
            components.append(UI.Box(flex=Axis.HORIZONTAL)[
                UI.Text(f'{line_num} '),
                UI.Text(Colors.hex('-  ', fg_color)),
                UI.Text(Colors.hex(delta, fg_color)),
            ])
            old_line_num += 1
        elif line.startswith('+'):
            line_num = f"{new_line_num:>4}"
            fg_color = Theme.FADED_GREEN if rejected else Theme.GREEN
            components.append(UI.Box(flex=Axis.HORIZONTAL)[
                UI.Text(f'{line_num} '),
                UI.Text(Colors.hex('+  ', fg_color)),
                UI.Text(Colors.hex(delta, fg_color)),
            ])
            new_line_num += 1
        elif line.startswith(' '):
            line_num = f"{old_line_num:>4}"
            delta = f'   {delta}'
            components.append(UI.Box(flex=Axis.HORIZONTAL)[UI.Text(f'{line_num} '), UI.Text(delta)])
            old_line_num += 1
            new_line_num += 1
        if not line.endswith('\n'):
            components.append(UI.Box(flex=Axis.HORIZONTAL)[UI.Text(f'{line_num} '), UI.Text('\\ No newline at end of file')])

    return UI.Box()[components]
