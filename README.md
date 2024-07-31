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

# Attach a file
$ ask -f ~/shakespeare.txt "No yapping: What are the first three stories in this collection?"

# Make a new file
$ ask -o ~/astronauts.py "No yapping: Write a python script that queries the astronauts API and prints the astronauts"

# Edit a file
$ ask -e ~/astronauts.py "Make this into a tkinter window"

# Chat mode
$ ask -c
```