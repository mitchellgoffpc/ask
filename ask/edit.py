import re
import difflib
from pathlib import Path
from collections import defaultdict
from typing import Iterator

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

EDIT_SYSTEM_PROMPT = """
    You are a world-class AI programming assistent.
    When asked to modify files, you should return the files with the requested changes.
    If a file is very long and you want to leave some parts unchanged, add a line with [UNCHANGED] to denote that the code in between shouldn't be changed.
    Don't add comments like '... rest of the code remains unchanged', just get to a natural breaking point
    and then add an [UNCHANGED] and move onto the next section that you want to modify.
    Be sure to include some surrounding context in each section so I know where it's supposed to go.
    Always add the file path above each edit.
    Write clean code, don't use too many comments.
""".replace('\n    ', ' ').strip()  # dedent and strip

UDIFF_SYSTEM_PROMPT = """
    You are a world-class AI programming assistent.
    When asked to modify files, you should return edits in the style of a unified diff patch, similar to what `diff -U0` would produce.
    Start each hunk of changes with a `@@ ... @@` line, and be sure to include some surrounding context in each hunk so I know where it's supposed to go.
    You don't need to include line numbers or timestamps, just the content of the patch.
    Always add the file path above each edit.
    Write clean code, don't use too many comments.
""".replace('\n    ', ' ').strip()


def get_diff_lines(expected: str, actual: str, file_path: str | Path) -> list[tuple[str, str]]:
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = difflib.unified_diff(expected_lines, actual_lines, fromfile=f'a/{file_path}', tofile=f'b/{file_path}')

    diff_lines = []
    for line in diff:
        if line.startswith('+'):
            color = GREEN
        elif line.startswith('-'):
            color = RED
        elif line.startswith('^'):
            color = YELLOW
        else:
            color = ''

        diff_lines.append((line, color))
        if not line.endswith('\n'):
            diff_lines.append(("\\ No newline at end of file\n", color))

    return diff_lines

def format_diff(expected: str, actual: str, file_path: str | Path) -> str:
    return ''.join(line for line, _ in get_diff_lines(expected, actual, file_path))

def print_diff(expected: str, actual: str, file_path: str | Path) -> None:
    for line, color in get_diff_lines(expected, actual, file_path):
        print(f"{color}{line}{RESET}", end='')

def add_trailing_newlines(original: str, edited: str) -> str:
    original_trailing_newlines = len(original) - len(original.rstrip('\n'))
    return edited.rstrip('\n') + '\n' * original_trailing_newlines

def extract_code_blocks(response: str) -> Iterator[tuple[str, str]]:
    yield from re.findall(r'^(\S+)\n+```[\w]*\n(.*?)\n```', response, re.DOTALL | re.MULTILINE)

def extract_first_code_block(response: str) -> tuple[str | None, str]:
    code_blocks = list(extract_code_blocks(response))
    return code_blocks[0] if code_blocks else (None, response)


# Section patch

def find_most_unique_match(original_lines: list[str], section_lines: list[str]) -> difflib.Match:
    def find_all_matches(alo, ahi):
        if alo >= ahi:
            return []
        i, j, k = x = matcher.find_longest_match(alo, ahi, 0, len(section_lines))
        return [*find_all_matches(alo, i), x, *find_all_matches(i + k, ahi)] if k else []

    # First we find all possible matches
    matcher = difflib.SequenceMatcher(None, original_lines, section_lines)
    matching_blocks = find_all_matches(0, len(original_lines))

    # Then we group the matching blocks by (block.b, block.size) and find the group with the fewest matches
    candidates = defaultdict(list)
    for block in sorted(matching_blocks):
        candidates[(block.b, block.size)].append(block.a)
    j, k = min(candidates, key=lambda k: (len(candidates[k]), -k[1], k[0]))  # sort by (n_matches, -size, start_pos)
    return difflib.Match._make((candidates[j, k][0], j, k))  # return the first block from the winning group

def get_matching_blocks(original_lines: list[str], section_lines: list[str]) -> list[difflib.Match]:
    def find_matching_blocks(alo, ahi, blo, bhi, reverse):
        if alo >= ahi or blo >= bhi:
            return []
        if reverse:
            i, j, k = reverse_matcher.find_longest_match(la - ahi, la - alo, lb - bhi, lb - blo)
            i, j = la - i - k, lb - j - k
            x = difflib.Match._make((i, j, k))
        else:
            i, j, k = x = forward_matcher.find_longest_match(alo, ahi, blo, bhi)
        return [*find_matching_blocks(alo, i, blo, j, True), x, *find_matching_blocks(i + k, ahi, j + k, bhi, False)] if k else []

    # First we find the most unique match
    i, j, k = first_match = find_most_unique_match(original_lines, section_lines)

    # Then we expand outwards from that match to find all matching blocks.
    # We always want to find the closest matches to the starting block, so we use a reverse matcher to extend the match backwards.
    forward_matcher = difflib.SequenceMatcher(None, original_lines, section_lines)
    reverse_matcher = difflib.SequenceMatcher(None, original_lines[::-1], section_lines[::-1])
    la, lb = len(original_lines), len(section_lines)
    return [*find_matching_blocks(0, i, 0, j, True), first_match, *find_matching_blocks(i + k, la, j + k, lb, False)]

def starts_with_replacement(original_lines: list[str], section_lines: list[str], match: difflib.Match) -> bool:
    a = '\n'.join(original_lines[match.a - match.b:match.a])
    b = '\n'.join(section_lines[:match.b])
    return difflib.SequenceMatcher(None, a, b).ratio() > 0.5

def apply_section_edit(original: str, patch: str) -> str:
    original_lines = original.splitlines(keepends=True)
    patch_sections = re.split(r'.*\[UNCHANGED\].*', patch)
    output_lines = []
    start_idx = 0

    for section in patch_sections:
        section = section.lstrip('\n').rstrip('\t ')
        if not section.strip():
            continue
        section_lines = section.splitlines(keepends=True)
        matching_blocks = get_matching_blocks(original_lines[start_idx:], section_lines)

        if len(matching_blocks) > 0:
            first_match = next(match for match in matching_blocks if ''.join(section_lines[match.b:match.b + match.size]).strip())  # first non-empty match
            last_match = matching_blocks[-1]
            replace = starts_with_replacement(original_lines[start_idx:], section_lines, first_match)
            output_lines.extend(original_lines[start_idx:start_idx + first_match.a - (first_match.b if replace else 0)])
            output_lines.extend(section_lines)
            start_idx += last_match.a + last_match.size
        else:
            output_lines.extend(section_lines)  # If no match found, append the entire section

    if patch_sections and not patch_sections[-1].strip():  # if patch ends with [UNCHANGED], append the rest of the file
        output_lines.extend(original_lines[start_idx:])

    return add_trailing_newlines(original, ''.join(output_lines))


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

    return add_trailing_newlines(original, ''.join(lines))

def apply_udiff_edit(original: str, patch: str) -> str:
    try:
        return apply_patch(original, patch)
    except Exception as e:
        print(f"Error: Unable to parse the patch as a unified diff. {str(e)}")
        import traceback
        traceback.print_exc()
        return original


# Main edit function

def apply_edits(response: str, diff: bool) -> dict[Path, tuple[str, str]]:
    modifications = {}
    for file_path_str, code_block in extract_code_blocks(response):
        file_path = Path(file_path_str).expanduser()
        file_exists = file_path.exists()
        if file_exists:
            file_data = file_path.read_text()
            modified = apply_udiff_edit(file_data, code_block) if diff else apply_section_edit(file_data, code_block)
            user_prompt = f"Do you want to apply this edit to {file_path}? (y/n): "
        else:
            file_data = ""
            modified = code_block
            user_prompt = f"File {file_path} does not exist. Do you want to create it? (y/n): "

        print_diff(file_data, modified, file_path)
        user_input = input(user_prompt).strip().lower()
        if user_input == 'y':
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(modified)
            print(f"Saved edits to {file_path}" if file_exists else f"Created {file_path}")
            modifications[file_path] = (file_data, modified)

    return modifications


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
    _, patch_content = extract_first_code_block(patch_content)
    edited_content = apply_udiff_edit(original_content, patch_content) if args.diff else apply_section_edit(original_content, patch_content)

    print("Diff between original and edited content:")
    print_diff(original_content, edited_content, args.original)
