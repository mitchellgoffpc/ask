from collections import defaultdict

from ask.messages import Message, Usage, Text, ToolRequest, ToolResponse, Command
from ask.models import Model
from ask.ui.core.styles import Colors, Theme

def estimate_context_usage(messages: list[Message], model: Model) -> dict[str, int]:
    usage = {
        'system_prompt': 0,
        'tool_descriptors': 0,
        'tool_calls': 0,
        'memory_files': 0,
        'messages': 0,
    }
    system_section = True
    accumulated_messages: list[Message] = []
    last_usage: Usage | None = None

    for msg in messages:
        if isinstance(msg.content, Usage):
            if accumulated_messages and last_usage:
                tokens_to_distribute = last_usage.input + last_usage.cache_write + last_usage.cache_read
                char_counts = defaultdict(int)

                for m in accumulated_messages:
                    key = _classify_message(m, system_section)
                    char_counts[key] += _estimate_chars(m.content)

                total_chars = sum(char_counts.values())
                if total_chars > 0:
                    for key, chars in char_counts.items():
                        tokens = int(tokens_to_distribute * chars / total_chars)
                        usage[key] = usage[key] + tokens

            last_usage = msg.content
            accumulated_messages = []
            system_section = False
        else:
            accumulated_messages.append(msg)

    return usage

def _classify_message(msg: Message, system_section: bool) -> str:
    from ask.commands import DocsCommand
    if system_section:
        if isinstance(msg.content, ToolRequest):
            return 'tool_descriptors'
        elif isinstance(msg.content, DocsCommand):
            return 'memory_files'
        elif isinstance(msg.content, ToolResponse):
            return 'memory_files'
        else:
            return 'system_prompt'
    if isinstance(msg.content, ToolRequest):
        return 'tool_calls'
    return 'messages'

def _estimate_chars(content) -> int:
    match content:
        case Text(text=text):
            return len(text)
        case ToolRequest(arguments=args):
            return sum(len(str(v)) for v in args.values())
        case ToolResponse(response=Text(text=text)):
            return len(text)
        case Command():
            return sum(_estimate_chars(m.content) for m in content.messages())
        case _:
            return 0

def format_context_usage(usage: dict[str, int], model: Model) -> str:
    total = sum(usage.values())
    max_tokens = model.context.max_length
    free_space = max_tokens - total
    percent = (total / max_tokens) * 100

    bar_width = 10
    filled = int((total / max_tokens) * bar_width)
    empty = bar_width - filled

    filled_icon = Colors.hex('⛁', Theme.BLUE)
    empty_icon = Colors.hex('⛀', Theme.DARK_GRAY)
    free_icon = Colors.hex('⛶', Theme.DARK_GRAY)

    bar = ' '.join([filled_icon] * filled + [empty_icon] * empty)

    lines = [
        f"Context Usage",
        f" {bar}   {model.name} · {_format_tokens(total)}/{_format_tokens(max_tokens)} tokens ({percent:.1f}%)",
    ]

    if total > 0:
        lines.append(f" {' '.join([free_icon] * bar_width)}")
        lines.append(f" {' '.join([free_icon] * bar_width)}   Estimated usage by category")

        categories = [
            ('system_prompt', 'System prompt', Theme.PURPLE),
            ('tool_descriptors', 'Tool descriptors', Theme.BLUE),
            ('tool_calls', 'Tool calls', Theme.CYAN),
            ('memory_files', 'Memory files', Theme.ORANGE),
            ('messages', 'Messages', Theme.GREEN),
        ]

        for key, label, color in categories:
            tokens = usage[key]
            if tokens > 0:
                cat_percent = (tokens / max_tokens) * 100
                icon = Colors.hex('⛁', color)
                lines.append(f" {' '.join([free_icon] * bar_width)}   {icon} {label}: {_format_tokens(tokens)} tokens ({cat_percent:.1f}%)")

        free_percent = (free_space / max_tokens) * 100
        lines.append(f" {' '.join([free_icon] * bar_width)}   {free_icon} Free space: {_format_tokens(free_space)} ({free_percent:.1f}%)")

    return '\n'.join(lines)

def _format_tokens(count: int) -> str:
    if count >= 1000:
        return f"{count / 1000:.1f}k".rstrip('0').rstrip('.')
    return str(count)
