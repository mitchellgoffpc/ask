import curses
from dataclasses import dataclass, field

@dataclass
class Cell:
  lines: list = field(default_factory=lambda: [""])
  height: int = 10
  file: str = None

def ctrl(char):
  return ord(char) - 96

def get_line_height(line, win_width):
  return max(1, (len(line) + win_width - 1) // win_width)

def get_cell_height(cell, win_width):
  return max(10, sum(get_line_height(line, win_width) for line in cell.lines))


# Rendering

def gui_write(stdscr, cells, cursor_pos):
  stdscr.clear()

  # Write cell content
  offset = 0
  active_cell_idx, active_row_idx, active_col_idx = cursor_pos
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
  stdscr.move(offset + active_row_idx + 1, active_col_idx)
  stdscr.refresh()

def gui_write_cell(stdscr, cell, cursor_pos, offset):
  _, row_idx, col_idx = cursor_pos
  screen_row_idx = offset + row_idx + 1
  for i in range(cell.height):
    stdscr.move(offset + 1 + i, 0)
    stdscr.clrtoeol()
    if i < len(cell.lines):
      stdscr.addstr(cell.lines[i])
  stdscr.move(screen_row_idx, min(col_idx, len(cell.lines[row_idx])))
  stdscr.refresh()


# Edit mode

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
    redraw_cell = False

    # Cursor movement commands
    if char in (curses.KEY_LEFT, ctrl('b')):
      col_idx = min(col_idx, len(cell.lines[row_idx]))
      col_idx = max(0, col_idx - 1)
    elif char in (curses.KEY_RIGHT, ctrl('f')):
      col_idx = min(len(line), col_idx + 1)
    elif char in (curses.KEY_UP, ctrl('p')):
      row_idx = max(0, row_idx - 1)
    elif char in (curses.KEY_DOWN, ctrl('n')):
      row_idx = min(len(cell.lines) - 1, row_idx + 1)
    elif char == ctrl('a'):
      col_idx = 0
    elif char == ctrl('e'):
      col_idx = len(line)
    elif char == 27:  # escape key
      break

    # Editing commands
    elif char == ctrl('k'):
      cell.lines[row_idx] = line[:col_idx]
    elif char in (10, ctrl('o')):  # enter key
      if col_idx < len(line):  # split the line at the cursor position
        cell.lines = cell.lines[:row_idx] + [line[:col_idx], line[col_idx:]] + cell.lines[row_idx+1:]
      else:  # start a new line
        cell.lines = cell.lines[:row_idx+1] + [""] + cell.lines[row_idx+1:]
      if char == 10:
        row_idx += 1
        col_idx = 0
      redraw_cell = True
    elif char in (curses.KEY_BACKSPACE, 127):  # backspace key
      if col_idx > 0:  # delete the previous character
        col_idx = min(col_idx, len(cell.lines[row_idx]))
        cell.lines[row_idx] = line[:col_idx-1] + line[col_idx:]
        col_idx -= 1
      elif row_idx > 0:  # delete line break
        col_idx = min(col_idx, len(cell.lines[row_idx]))
        prev_line, current_line = cell.lines[row_idx - 1], cell.lines[row_idx]
        cell.lines = cell.lines[:row_idx - 1] + [prev_line + current_line] + cell.lines[row_idx + 1:]
        row_idx -= 1
        col_idx = len(prev_line)
        redraw_cell = True
    else:
      col_idx = min(col_idx, len(cell.lines[row_idx]))
      cell.lines[row_idx] = line[:col_idx] + chr(char) + line[col_idx:]
      col_idx += 1

    # Redraw line, cell, or entire screen if necessary
    new_height = get_cell_height(cell, win_width)
    if new_height != cell.height:
      cell.height = new_height
      gui_write(stdscr, cells, (cell_idx, row_idx, col_idx))
    elif redraw_cell:
      gui_write_cell(stdscr, cell, (cell_idx, row_idx, col_idx), offset)
    else:
      screen_row_idx = offset + row_idx + 1
      stdscr.move(screen_row_idx, 0)
      stdscr.clrtoeol()
      stdscr.addstr(screen_row_idx, 0, cell.lines[row_idx])
      stdscr.move(screen_row_idx, min(col_idx, len(cell.lines[row_idx])))
      stdscr.refresh()

  return cells, (cell_idx, -1, 0)


# Normal mode

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
  elif key in (ord('k'), curses.KEY_UP):
    cell_idx = max(0, cell_idx - 1)

  # Cell addition commands
  elif key == ord('a'):  # add cell before
    cells.insert(cell_idx, Cell())
  elif key == ord('b'):  # add cell after
    cells.insert(cell_idx + 1, Cell())
    cell_idx += 1

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


def main_loop(stdscr, cells, cursor_pos=(0, -1, 0)):
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
  curses.wrapper(lambda stdscr: main_loop(stdscr, [Cell()]))
