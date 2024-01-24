import curses
from dataclasses import dataclass, field

@dataclass
class Cell:
  lines: list = field(default_factory=list)
  height: int = 10
  file: str = None


def edit(stdscr, cells, cursor_pos):
  win_height, win_width = stdscr.getmaxyx()
  cell_idx, _, _ = cursor_pos
  row_idx, col_idx = 0, 0
  offset = sum(cell.height + 1 for cell in cells[:cell_idx])
  stdscr.move(offset + 1, col_idx)

  while True:
    cell = cells[cell_idx]
    line = cell.lines[row_idx]
    char = stdscr.getch()

    if char == curses.KEY_LEFT:
      col_idx = max(0, col_idx - 1)
    elif char == curses.KEY_RIGHT:
      col_idx = min(len(line), col_idx + 1)
    elif char == curses.KEY_UP:
      row_idx = min(0, row_idx + 1)
    elif char == curses.KEY_DOWN:
      row_idx = min(len(cell.lines) - 1, row_idx + 1)
    elif char == 27:  # escape key
      break
    elif char == 10:  # enter key
      cell.lines = cell.lines[:row_idx+1] + [Cell()] + cell.lines[row_idx+1:]
      row_idx, col_idx = row_idx + 1, 0
    elif char in (curses.KEY_BACKSPACE, 127):  # backspace key
      if col_idx > 0:
        cell.lines[row_idx] = line[:col_idx-1] + line[col_idx:]
        col_idx -= 1
    else:
      cell.lines[row_idx] = line[:col_idx] + chr(char) + line[col_idx:]
      col_idx += 1

    screen_row_idx = offset + row_idx + 1
    stdscr.move(screen_row_idx, 0)
    stdscr.clrtoeol()
    stdscr.addstr(screen_row_idx, 0, cell.lines[row_idx])
    stdscr.move(screen_row_idx, min(col_idx, len(cell.lines[row_idx])))

  return cells, (cell_idx, row_idx, col_idx)


def gui_write(stdscr, cells, cursor_pos):
  stdscr.clear()

  # Write cell content
  offset = 0
  active_cell_idx, _, _ = cursor_pos
  for cell_idx, cell in enumerate(cells):
    stdscr.attron(curses.color_pair(2 if cell_idx == active_cell_idx else 1))
    stdscr.addstr(offset, 0, "-- CELL --".ljust(stdscr.getmaxyx()[1]))
    stdscr.attroff(curses.color_pair(1))
    for row_idx, line in enumerate(cell.lines):
      for col_idx, char in enumerate(line):
        stdscr.addch(offset + row_idx + 1, col_idx, char)  # Start from the second line, as the first line is the top bar
    offset += cell.height + 1

  cell_idx, _, _ = cursor_pos
  offset = sum(cell.height + 1 for cell in cells[:cell_idx])
  stdscr.move(offset, 0)
  stdscr.refresh()


def getcmdline(stdscr):
  """Reads a line from the terminal and updates it at the bottom of the screen."""
  win_height, win_width = stdscr.getmaxyx()
  cmd_win = curses.newwin(1, win_width, win_height - 1, 0)
  input_str = ""
  while True:
    cmd_win.clear()
    cmd_win.addstr(":" + input_str)
    cmd_win.refresh()
    char = cmd_win.getch()
    if char == 127 and len(input_str) == 0:  # backspace key and string is empty
      input_str = ""
      break
    elif char == 10:  # enter key
      break
    elif char == 127:  # backspace key
      input_str = input_str[:-1]
    else:
      input_str += chr(char)
  return input_str


def normal_cmd(stdscr, cells, cursor_pos):
  cell_idx, row_idx, col_idx = cursor_pos
  cell = cells[cell_idx]
  line = cell.lines[row_idx]
  key = stdscr.getch()

  # Cursor movement commands
  if key in (ord('j'), curses.KEY_DOWN):
    cell_idx = min(len(cells) - 1, cell_idx + 1)
  if key in (ord('k'), curses.KEY_UP):
    cell_idx = max(0, cell_idx - 1)

  # Misc commands
  elif key in (ord("i"), 10):  # enter key
    cells, (cell_idx, row_idx, col_idx) = edit(stdscr, cells, cursor_pos)
  elif key == ord(':'):  # enter command mode
    cmd = getcmdline(stdscr)
    if cmd.lower() == "q":
      curses.endwin()
      exit()
    else:
      stdscr.addstr("Unknown command. Use 'q' to quit.\n")

  cursor_pos = (cell_idx, row_idx, col_idx)
  gui_write(stdscr, cells, cursor_pos)
  return cells, cursor_pos


def main_loop(stdscr, cells, cursor_pos=(0, 0, 0)):
  curses.set_escdelay(25)
  curses.use_default_colors()
  curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
  curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)
  gui_write(stdscr, cells, cursor_pos)
  while True:
    buffer, cursor_pos = normal_cmd(stdscr, cells, cursor_pos)


def interactive(question, model):
  curses.wrapper(lambda stdscr: main_loop(stdscr, [Cell(lines=["foo"]), Cell(lines=["bar"])]))

if __name__ == "__main__":
  curses.wrapper(lambda stdscr: main_loop(stdscr, [Cell(lines=[""])]))
