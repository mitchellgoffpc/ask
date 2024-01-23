import curses

def edit(stdscr, buffer, cursor_pos):
  """Handles insert mode. Allows user to modify the buffer and returns when escape key is pressed."""
  win_height, win_width = stdscr.getmaxyx()
  stdscr.addstr(win_height - 1, 0, "-- INSERT --")
  stdscr.move(*cursor_pos)
  i, j = cursor_pos

  while True:
    char = stdscr.getch()

    if char == curses.KEY_LEFT:
      j = max(0, j - 1)
    elif char == curses.KEY_RIGHT:
      j = min(len(buffer[i]), j + 1)
    elif char == curses.KEY_UP or char == curses.KEY_DOWN:
      continue  # Ignore up and down keys in insert mode
    elif char == 27:  # escape key
      break
    elif char == 10:  # enter key
      buffer = buffer[:i+1] + [''] + buffer[i+1:]
      i += 1
      j = 0
    elif char in (curses.KEY_BACKSPACE, 127):  # backspace key
      if j > 0:
        buffer[i] = buffer[i][:j-1] + buffer[i][j:]
        j -= 1
    else:
      buffer[i] = buffer[i][:j] + chr(char) + buffer[i][j:]
      j += 1

    stdscr.move(i, 0)
    stdscr.clrtoeol()
    stdscr.addstr(i, 0, buffer[i])
    stdscr.move(i, min(j, len(buffer[i])))

  return buffer, (i, j)

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

def gui_write(stdscr, buffer, cursor_pos):
  stdscr.clear()
  for i, line in enumerate(buffer):
    for j, char in enumerate(line):
      stdscr.addch(i, j, char)
  i, j = cursor_pos
  stdscr.move(i, min(j, len(buffer[i])))
  stdscr.refresh()

def normal_cmd(stdscr, buffer, cursor_pos):
  """Handles command processing in normal mode."""
  current_line = buffer[0]
  key = stdscr.getch()
  i, j = cursor_pos

  # Cursor movement commands
  if key in (ord('h'), curses.KEY_LEFT):
    j = max(0, j - 1)
  elif key in (ord('j'), curses.KEY_DOWN):
    i = min(len(buffer) - 1, i + 1)
  elif key in (ord('k'), curses.KEY_UP):
    i = max(0, i - 1)
  elif key in (ord('l'), curses.KEY_RIGHT):
    j = min(len(current_line) - 1, j + 1)
  elif key == ord('0'):
    j = 0
  elif key == ord('$'):
    j = len(current_line) - 1

  # Misc commands
  elif key == ord("i"):
    buffer, (i, j) = edit(stdscr, buffer, cursor_pos)
  elif key == ord(':'):  # enter command mode
    cmd = getcmdline(stdscr)
    if cmd.lower() == "q":
      curses.endwin()
      exit()
    else:
      stdscr.addstr("Unknown command. Use 'q' to quit.\n")
  else:
    return buffer, cursor_pos

  cursor_pos = (i, j)
  gui_write(stdscr, buffer, cursor_pos)
  return buffer, cursor_pos

def main_loop(stdscr, buffer, cursor_pos=(0, 0)):
  curses.use_default_colors()
  curses.set_escdelay(25)
  gui_write(stdscr, buffer, cursor_pos)
  while True:
    buffer, cursor_pos = normal_cmd(stdscr, buffer, cursor_pos)

def interactive(question, model):
  curses.wrapper(lambda stdscr: main_loop(stdscr, [question]))

if __name__ == "__main__":
  curses.wrapper(lambda stdscr: main_loop(stdscr, [""]))
