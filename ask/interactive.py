import curses

def edit(stdscr, buffer, cursor_pos):
  """Handles insert mode. Allows user to modify the buffer and returns when escape key is pressed."""
  win_height, win_width = stdscr.getmaxyx()
  stdscr.addstr(win_height - 1, 0, "-- INSERT --")
  stdscr.move(0, cursor_pos)
  i = cursor_pos

  while True:
    char = stdscr.getch()

    # Handle arrow keys
    if char == curses.KEY_LEFT:
      i = max(0, i - 1)
    elif char == curses.KEY_RIGHT:
      i = min(len(buffer), i + 1)
    elif char == curses.KEY_UP or char == curses.KEY_DOWN:
      continue  # Ignore up and down keys in insert mode
    elif char == 27:  # escape key
      break
    elif char == 127:  # backspace key
      if i > 0:
        buffer = buffer[:i-1] + buffer[i:]
        i -= 1
    else:
      buffer = buffer[:i] + chr(char) + buffer[i:]
      i += 1

    stdscr.clear()
    stdscr.addstr(win_height - 1, 0, "-- INSERT --")
    stdscr.addstr(0, 0, buffer)
    stdscr.move(0, i)

  return buffer, i  # Return the updated buffer and cursor position

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
  for i, char in enumerate(buffer):
    stdscr.addch(0, i, char)
  stdscr.move(0, cursor_pos)
  curses.curs_set(1)
  stdscr.refresh()

def normal_cmd(stdscr, buffer, cursor_pos=0):
  """Handles command processing in normal mode."""
  key = stdscr.getch()
  if key in (ord('h'), curses.KEY_LEFT):
    cursor_pos = max(0, cursor_pos - 1)
  elif key in (ord('j'), curses.KEY_DOWN):
    cursor_pos = min(len(buffer) - 1, cursor_pos + 1)
  elif key in (ord('k'), curses.KEY_UP):
    cursor_pos = max(0, cursor_pos - 1)
  elif key in (ord('l'), curses.KEY_RIGHT):
    cursor_pos = min(len(buffer) - 1, cursor_pos + 1)
  elif key == ord("i"):
    buffer, i = edit(stdscr, buffer, cursor_pos)
  elif key == ord(':'):  # enter command mode
    cmd = getcmdline(stdscr)
    if cmd.lower() == "q":
      curses.endwin()
      exit()
    else:
      stdscr.addstr("Unknown command. Use 'q' to quit.\n")
  else:
    return buffer, cursor_pos

  gui_write(stdscr, buffer, cursor_pos)
  return buffer, cursor_pos

def main_loop(stdscr, buffer, cursor_pos=0):
  gui_write(stdscr, buffer, cursor_pos)
  while True:
    buffer, cursor_pos = normal_cmd(stdscr, buffer, cursor_pos)

def interactive(question, model):
  curses.wrapper(lambda stdscr: main_loop(stdscr, question))

if __name__ == "__main__":
  curses.wrapper(lambda stdscr: main_loop(stdscr, ""))
