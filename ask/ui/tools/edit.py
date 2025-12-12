from typing import ClassVar
from dataclasses import dataclass

from ask.models import Blob
from ask.prompts import get_relative_path
from ask.ui.core.components import Component, Box, Text
from ask.ui.core.diff import Diff
from ask.ui.core.markdown_ import highlight_code
from ask.ui.core.styles import Styles, Colors, Theme
from ask.ui.tools.base import ToolOutput, ToolOutputController, abbreviate

@dataclass
class EditToolOutput(ToolOutput):
    __controller__: ClassVar = lambda _: EditToolOutputController

class EditToolOutputController(ToolOutputController):
    def get_args(self) -> str:
        return get_relative_path(self.props.request.arguments['file_path'])

    def get_cancelled_message(self) -> Component:
        args = self.props.request.processed_arguments or {}
        operation = 'update' if args['old_content'] else 'write'
        return Box()[
            Text(Colors.hex(f"User rejected {operation} to {Styles.bold(get_relative_path(args['file_path']))}", Theme.RED)),
            Diff(diff=args['diff'], rejected=True)
        ]

    def get_completed_output(self, response: Blob) -> Component:
        args = self.props.request.processed_arguments or {}
        if not args['old_content']:
            num_lines = args['new_content'].count('\n') + 1
            status_line = f"Wrote {Styles.bold(str(num_lines))} lines to {Styles.bold(get_relative_path(args['file_path']))}"
            output = f"{status_line}\n{highlight_code(args['new_content'], file_path=str(args['file_path']))}"
            return Text(abbreviate(output, max_lines=8) if not self.props.expanded else output)
        else:
            num_additions = sum(1 for line in args['diff'] if line.startswith('+') and not line.startswith('+++'))
            num_deletions = sum(1 for line in args['diff'] if line.startswith('-') and not line.startswith('---'))
            addition_text = f"{Styles.bold(str(num_additions))} addition{'s' if num_additions != 1 else ''}"
            deletion_text = f"{Styles.bold(str(num_deletions))} removal{'s' if num_deletions != 1 else ''}"
            return Box()[
                Text(f"Updated {Styles.bold(get_relative_path(args['file_path']))} with {addition_text} and {deletion_text}"),
                Diff(diff=args['diff'])
            ]
