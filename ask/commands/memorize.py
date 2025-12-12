from asyncio import Task
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ask.messages import MessageTree
from ask.models import Message, Text, Command
from ask.prompts import get_agents_md_path

@dataclass(kw_only=True)
class MemorizeCommand(Command):
    @classmethod
    def create(cls, value: str, messages: MessageTree, head: UUID | None) -> tuple[UUID, list[Task]]:
        agents_path = get_agents_md_path()
        content = agents_path.read_text() if agents_path else ''
        if content and not content.endswith('\n'):
            content += '\n'
        agents_path = agents_path or Path.cwd() / "AGENTS.md"
        agents_path.write_text(content + f"- {value.strip()}\n")
        head = messages.add('user', head, MemorizeCommand(command=value.strip()))
        return head, []

    def messages(self) -> list[Message]:
        return [Message(role='user', content=Text(f"I've added the following to the AGENTS.md file:\n\n```{self.command}```"))]
