import re
import difflib
from pathlib import Path

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

UDIFF_SYSTEM_PROMPT = """
    You are an AI programming assistent. When asked to modify a file, you should return edits in the style of a unified diff patch, similar to what `diff -U0` would produce.
    Start each hunk of changes with a `@@ ... @@` line, and be sure to include some surrounding context in each hunk so I know where it's supposed to go.
    You don't need to include line numbers or timestamps, just the content of the patch.
""".replace('\n    ', ' ').strip()


def print_diff(expected: str, actual: str, file_path: str | Path) -> None:
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = difflib.unified_diff(expected_lines, actual_lines, fromfile=f'a/{file_path}', tofile=f'b/{file_path}')

    for line in diff:
        if line.startswith('+'):
            color = GREEN
        elif line.startswith('-'):
            color = RED
        elif line.startswith('^'):
            color = YELLOW
        else:
            color = ''

        print(f"{color}{line}{RESET}", end='')
        if not line.endswith('\n'):
            print(f"\n{color}\\ No newline at end of file{RESET}")

def extract_code_block(text: str) -> str:
    pattern = r'```(?:\w+)?\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


# Section patch

def apply_section_edit(original: str, patch: str) -> str:
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


# Unified diff patch

def apply_patch(original: str, patch: str) -> str:
    lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    for i, line in enumerate(patch_lines):
        if line.startswith("@@"):
            # Extract the context from the hunk
            context_lines = []
            for change in patch_lines[i + 1:]:
                if change.startswith("@@"):
                    break
                elif change.startswith(('-', ' ')):
                    context_lines.append(change[1:])
                elif not change or change.startswith('\n'):
                    context_lines.append(change)

            # Use difflib to find the best match for the context
            matcher = difflib.SequenceMatcher(None, lines, context_lines)
            match = matcher.find_longest_match(0, len(lines), 0, len(context_lines))
            current_line = match.a - match.b

            # Apply the changes
            removed = 0
            added = 0
            for change in patch_lines[i + 1:]:
                if change.startswith('@@'):
                    break
                elif change.startswith('-'):
                    lines.pop(current_line)
                    removed += 1
                elif change.startswith('+'):
                    lines.insert(current_line, change[1:])
                    current_line += 1
                    added += 1
                elif not change or change.startswith((' ', '\n')):
                    current_line += 1
                else:
                    raise ValueError(f"Invalid change line: {change!r}")

    return ''.join(lines)

def apply_udiff_edit(original: str, patch: str) -> str:
    try:
        patch = extract_code_block(patch)
        return apply_patch(original, patch)
    except Exception as e:
        print(f"Error: Unable to parse the patch as a unified diff. {str(e)}")
        import traceback
        traceback.print_exc()
        return original


# Entry point for testing

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Apply edits to a file and show the diff.")
    parser.add_argument("original", help="Path to the original file")
    parser.add_argument("patch", help="Path to the patch file")
    parser.add_argument("-d", "--diff", action="store_true", help="Interpret the patch as a unified diff")
    args = parser.parse_args()

    with open(args.original) as f:
        original_content = f.read()
    with open(args.patch) as f:
        patch_content = f.read()
    edited_content = apply_udiff_edit(original_content, patch_content) if args.diff else apply_section_edit(original_content, patch_content)

    print("Diff between original and edited content:")
    print_diff(original_content, edited_content, args.original)
