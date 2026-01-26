from ask.ui.core import Component, Text, Box, Axis, Colors, Theme


def Diff(diff: list[str], rejected: bool = False) -> Component:
    components: list[Component] = []
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
                components.append(Text(f"{Colors.hex(' ... ', Theme.GRAY)}"))
        elif line.startswith('-'):
            line_num = Colors.hex(f"{old_line_num:>4}", Theme.GRAY)
            bg_color = Theme.FADED_RED if rejected else Theme.DARK_RED
            components.append(Box(flex=Axis.HORIZONTAL)[
                Text(f'{line_num} '),
                Text(Colors.bg_hex(Colors.hex('-  ', Theme.WHITE), bg_color)),
                Text(Colors.bg_hex(Colors.hex(delta, Theme.WHITE), bg_color))
            ])
            old_line_num += 1
        elif line.startswith('+'):
            line_num = Colors.hex(f"{new_line_num:>4}", Theme.GRAY)
            bg_color = Theme.FADED_GREEN if rejected else Theme.DARK_GREEN
            components.append(Box(flex=Axis.HORIZONTAL)[
                Text(f'{line_num} '),
                Text(Colors.bg_hex(Colors.hex('+  ', Theme.WHITE), bg_color)),
                Text(Colors.bg_hex(Colors.hex(delta, Theme.WHITE), bg_color))
            ])
            new_line_num += 1
        elif line.startswith(' '):
            line_num = Colors.hex(f"{old_line_num:>4}", Theme.GRAY)
            delta = Colors.hex(f'   {delta}', Theme.WHITE)
            components.append(Box(flex=Axis.HORIZONTAL)[Text(f'{line_num} '), Text(delta)])
            old_line_num += 1
            new_line_num += 1
        if not line.endswith('\n'):
            components.append(Box(flex=Axis.HORIZONTAL)[Text(f'{line_num} '), Text('\\ No newline at end of file')])

    return Box()[components]
