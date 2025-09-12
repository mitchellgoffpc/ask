from collections import defaultdict
from uuid import UUID

from ask.models import MODELS_BY_NAME, Message, Usage


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return (f'{hours}h ' if hours else '') + (f'{minutes}m ' if minutes else '') + f'{seconds}s'

def get_usage_message(messages: dict[UUID, Message], total_duration_api: float, total_duration_wall: float) -> str:
    usages_by_model = defaultdict(list)
    for msg in messages.values():
        if isinstance(msg.content, Usage) and msg.content.model:
            usages_by_model[msg.content.model.name].append(msg.content)

    total_cost = 0.
    rows: list[tuple[str, str]] = []
    for model_name, usages in usages_by_model.items():
        total_in = sum(u.input for u in usages)
        total_out = sum(u.output for u in usages)
        total_cache_w = sum(u.cache_write for u in usages)
        total_cache_r = sum(u.cache_read for u in usages)
        if p := MODELS_BY_NAME[model_name].pricing:
            cost = total_in * p.input + total_cache_w * p.cache_write + total_cache_r * p.cache_read + total_out * p.output
            total_cost += cost
            cost_str = f" (${cost / 1_000_000:,.4f})" if len(usages_by_model) > 1 else ""
        else:
            cost_str = " (no pricing)"
        usage_str = f"{total_in:,} input, {total_out:,} output, {total_cache_r:,} cache read, {total_cache_w:,} cache write" + cost_str
        rows.append((f"    {model_name}", usage_str))

    rows = [
        ("Total cost", f"${total_cost / 1_000_000:,.4f}"),
        ("Total duration (API)", f"{format_duration(total_duration_api)}"),
        ("Total duration (wall)", f"{format_duration(total_duration_wall)}"),
        ("Usage by model", "" if usages_by_model else "(no usage)"),
        *rows
    ]
    max_title_len = max(len(title) + 1 for title, _ in rows)
    return '\n'.join(f"{title + ':':<{max_title_len}}  {value}" for title, value in rows)
