from ask.tools import BashTool, EditTool, GlobTool, GrepTool, ListTool, MultiEditTool, PythonTool, ReadTool, WriteTool
from ask.ui.tools.bash import BashToolOutput
from ask.ui.tools.edit import EditToolOutput
from ask.ui.tools.glob import GlobToolOutput
from ask.ui.tools.grep import GrepToolOutput
from ask.ui.tools.list import ListToolOutput
from ask.ui.tools.python import PythonToolOutput
from ask.ui.tools.read import ReadToolOutput

TOOL_COMPONENTS = {
    BashTool.name: BashToolOutput,
    EditTool.name: EditToolOutput,
    GlobTool.name: GlobToolOutput,
    GrepTool.name: GrepToolOutput,
    ListTool.name: ListToolOutput,
    MultiEditTool.name: EditToolOutput,
    PythonTool.name: PythonToolOutput,
    ReadTool.name: ReadToolOutput,
    WriteTool.name: EditToolOutput,
}

__all__ = [
    'TOOL_COMPONENTS',
    'BashToolOutput', 'EditToolOutput', 'GlobToolOutput', 'GrepToolOutput', 'ListToolOutput', 'PythonToolOutput', 'ReadToolOutput',
]
