import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from ask.commands.bash import BashCommand
from ask.commands.python import PythonCommand
from ask.prompts import COMMAND_CAVEAT_MESSAGE, load_prompt_file, get_relative_path
from ask.models import MODELS_BY_NAME, Model, Message, Blob, Text, ToolRequest, ToolResponse, Command, Usage
from ask.tools import ToolCallStatus
from ask.tree import MessageTree, MessageEncoder, message_decoder

@dataclass
class SlashCommand(Command):
    output: str = ''
    error: str = ''

    def messages(self) -> list[Message]:
        messages = [
            Message(role='user', content=Text(COMMAND_CAVEAT_MESSAGE)),
            Message(role='user', content=Text(f"<slash-command>{self.command}</slash-command>"))]
        if self.output or not self.error:
            messages.append(Message(role='user', content=Text(f"<slash-command-output>\n{self.output}\n</slash-command-output>")))
        if self.error:
            messages.append(Message(role='user', content=Text(f"<slash-command-error>\n{self.error}\n</slash-command-error>")))
        return messages

@dataclass
class InitCommand(SlashCommand):
    def messages(self) -> list[Message]:
        return [Message(role='user', content=Text(load_prompt_file('init.toml')['prompt']))]

@dataclass
class FilesCommand(SlashCommand):
    file_contents: dict[Path, Blob] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.output = '\n'.join(f'Read {get_relative_path(path)}' for path in self.file_contents.keys())

    def render_command(self) -> str:
        return self.command or f'Attached {len(self.file_contents)} files'

    def messages(self) -> list[Message]:
        file_list = '\n'.join(f'- {path}' for path in self.file_contents.keys())
        messages = [Message(role='user', content=Text(f"Take a look at these files:\n{file_list}"))]
        for file_path, file_data in self.file_contents.items():
            call_id = str(uuid4())
            tool_args = {'file_path': str(Path(file_path).absolute().as_posix())}
            messages.append(Message(role='assistant', content=ToolRequest(call_id=call_id, tool='Read', arguments=tool_args)))
            messages.append(Message(role='user', content=ToolResponse(call_id=call_id, tool='Read', response=file_data, status=ToolCallStatus.COMPLETED)))
        if self.command:
            messages.append(Message(role='user', content=Text(self.command)))
        return messages

@dataclass(kw_only=True)
class DocsCommand(Command):
    command: str = ''
    prompt_key: str
    file_path: Path
    file_contents: str

    def messages(self) -> list[Message]:
        content = load_prompt_file('docs.toml')[self.prompt_key].format(file_path=self.file_path.resolve(), file_contents=self.file_contents)
        return [Message(role='user', content=Text(content))]


# /model

def switch_model(model_name: str, current_model: Model, messages: MessageTree, head: UUID | None) -> tuple[UUID | None, Model]:
    if not model_name:
        model_list = '\n'.join(f"  {name} ({model.api.display_name})" for name, model in MODELS_BY_NAME.items())
        head = messages.add('user', head, SlashCommand(command='/model', output=f"Available models:\n{model_list}"))
    elif model_name not in MODELS_BY_NAME:
        head = messages.add('user', head, SlashCommand(command=model_name, error=f"Unknown model: {model_name}"))
    elif model_name != current_model.name:
        head = messages.add('user', head, SlashCommand(command=model_name, output=f"Switched from {current_model.name} to {model_name}"))
        current_model = MODELS_BY_NAME[model_name]
    return head, current_model


# /save + /load

def save_messages(path: str, messages: MessageTree, head: UUID | None) -> UUID:
    if path:
        try:
            Path(path).write_text(json.dumps({'head': head, 'messages': messages.dump()}, indent=2, cls=MessageEncoder))
            return messages.add('user', head, SlashCommand(command=f'/save {path}', output=f'Saved messages to {path}'))
        except Exception as e:
            return messages.add('user', head, SlashCommand(command=f'/save {path}', error=str(e)))
    else:
        return messages.add('user', head, SlashCommand(command='/save', error='No file path supplied'))

def load_messages(path: str, messages: MessageTree, head: UUID | None) -> UUID:
    if path:
        try:
            data = json.loads(Path(path).read_text(), object_hook=message_decoder)
            messages.load(data['messages'])
            assert isinstance(data['head'], UUID)
            return data['head']
        except Exception as e:
            return messages.add('user', head, SlashCommand(command=f'/load {path}', error=str(e)))
    else:
        return messages.add('user', head, SlashCommand(command='/load', error='No file path supplied'))


# /usage

def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return (f'{hours}h ' if hours else '') + (f'{minutes}m ' if minutes else '') + f'{seconds}s'

def get_usage(messages: dict[UUID, Message], total_duration_api: float, total_duration_wall: float) -> str:
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


__all__ = [
    "BashCommand",
    "DocsCommand",
    "FilesCommand",
    "FormatCommand",
    "InitCommand",
    "PythonCommand",
    "SlashCommand",
    "save_messages",
    "load_messages",
    "switch_model",
    "get_usage",
]
