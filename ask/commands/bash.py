import asyncio
from asyncio import Task
from dataclasses import dataclass, replace
from uuid import UUID

from ask.messages import Command, Message, Text, ToolCallStatus
from ask.prompts import COMMAND_CAVEAT_MESSAGE
from ask.tree import MessageTree


@dataclass
class BashCommand(Command):
    stdout: str = ''
    stderr: str = ''
    status: ToolCallStatus = ToolCallStatus.PENDING

    @classmethod
    async def run(cls, value: str, messages: MessageTree, uuid: UUID, command: 'BashCommand') -> None:
        try:
            process = await asyncio.create_subprocess_shell(value, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            status = ToolCallStatus.COMPLETED if process.returncode == 0 else ToolCallStatus.FAILED
            messages.update(uuid, replace(command, stdout=stdout.decode().strip('\n'), stderr=stderr.decode().strip('\n'), status=status))
        except asyncio.CancelledError:
            messages.update(uuid, replace(command, status=ToolCallStatus.CANCELLED))

    @classmethod
    def create(cls, value: str, messages: MessageTree, head: UUID | None) -> tuple[UUID, list[Task]]:
        command = BashCommand(command=value)
        head = messages.add('user', head, command)
        task = asyncio.create_task(cls.run(value, messages, head, command))
        return head, [task]

    def messages(self) -> list[Message]:
        if self.status is ToolCallStatus.CANCELLED:
            output = "[Request interrupted by user]"
        else:
            output = f"<bash-stdout>\n{self.stdout}\n</bash-stdout>\n<bash-stderr>\n{self.stderr}\n</bash-stderr>"
        return [
            Message(role='user', content=Text(COMMAND_CAVEAT_MESSAGE)),
            Message(role='user', content=Text(f"<bash-stdin>{self.command}</bash-stdin>")),
            Message(role='user', content=Text(output))]
