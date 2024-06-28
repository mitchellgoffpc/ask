import re
import difflib

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

EDIT_SYSTEM_PROMPT = """
    You are an AI programming assistent. When asked to modify a file, you should return the file with the requested changes.
    If the file is very long and you want to leave some parts unchanged, add a line with [UNCHANGED] to denote that the code in between shouldn't be changed.
    Don't add comments like '... rest of the code remains unchanged', just get to a natural breaking point
    and then add an [UNCHANGED] and move onto the next section that you want to modify.
    Be sure to include some surrounding context in each section so I know where it's supposed to go.
""".replace('\n    ', ' ').strip()  # dedent and strip

def print_diff(expected, actual, file_path):
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = difflib.unified_diff(expected_lines, actual_lines, fromfile=f'a/{file_path}', tofile=f'b/{file_path}')

    for line in diff:
        if line.startswith('+'):
            print(f"{GREEN}{line}{RESET}", end='')
        elif line.startswith('-'):
            print(f"{RED}{line}{RESET}", end='')
        elif line.startswith('^'):
            print(f"{YELLOW}{line}{RESET}", end='')
        else:
            print(line, end='')

def extract_code_block(text):
    pattern = r'```(?:\w+)?\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def apply_edit(original, patch):
    patch = extract_code_block(patch)
    original_lines = original.splitlines(keepends=True)
    patch_sections = patch.split('[UNCHANGED]')
    output_lines = []
    start_idx = 0

    for section in patch_sections:
        section = section.lstrip('\n')
        if not section.strip():
            continue
        section_lines = section.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, original_lines[start_idx:], section_lines)
        ops = matcher.get_opcodes()
        new_start_idx = start_idx
        for i, (tag, alo, ahi, blo, bhi) in enumerate(ops):
            if i == 0 and tag == 'delete':
                output_lines.extend(original_lines[start_idx + alo:start_idx + ahi])
            elif tag in ('insert', 'replace', 'equal'):
                output_lines.extend(section_lines[blo:bhi])
                new_start_idx = start_idx + ahi

        start_idx = new_start_idx

    if patch_sections and not patch_sections[-1].strip():  # Ends with an [UNCHANGED]
        output_lines.extend(original_lines[start_idx:])
    return ''.join(output_lines)
