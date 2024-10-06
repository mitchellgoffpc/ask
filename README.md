# Ask

Ask is a CLI tool for querying and editing files with LLMs

### Installation

```sh
python3 -m pip install git+https://github.com/mitchellgoffpc/ask.git
```

### Usage

```sh
# Select a model
$ ask -m opus "What is the capital of france?"

# Write code
$ ask "Create a new file astronauts.py that queries the astronauts API and prints the astronauts"

# Attach and/or edit a file
$ ask -f astronauts.py "Make this into a tkinter window"

# Fix bugs
ask "I'm getting ImportError: dlopen(/Users/mitchell/.pyenv/versions/3.12.2/lib/python3.12/lib-dynload/_tkinter.cpython-312-darwin.so, 0x0002): Library not loaded: /opt/homebrew/opt/tcl-tk/lib/libtk8.6.dylib when I try to import tkinter in python, what can I do?"

# Chat mode
$ ask -c
```

### Notes

The default model is currently `claude-3-5-sonnet-20240620`.