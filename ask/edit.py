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
    You are being run in an interactive file editing scaffold.
    The user will pass any files they're working on inside of <file name="file-name"> XML tags.
    To edit files, you should reply with <edit name="file-name"> XML tags containing the file contents with the requested changes.
    If a file is very long and you want to leave some parts unchanged, add an [UNCHANGED] line to the edit to denote a section of code that shouldn't be changed.
    Be sure to include some surrounding context in each section so I know where it's supposed to go.
    Write clean code, don't use too many comments.
""".replace('\n    ', ' ').strip()  # dedent and strip


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
    yield from re.findall(r'^<edit name="(\S+)">\n(.*?)\n</edit>', response, re.DOTALL | re.MULTILINE)

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
        matching_blocks = [match for match in matching_blocks if ''.join(section_lines[match.b:match.b + match.size]).strip()]  # ignore empty matches

        if len(matching_blocks) > 0:
            first_match = matching_blocks[0]
            last_match = matching_blocks[-1]
            replace = starts_with_replacement(original_lines[start_idx:], section_lines, first_match)
            output_lines.extend(original_lines[start_idx:start_idx + first_match.a - (first_match.b if replace else 0)])
            output_lines.extend(section_lines)
            start_idx += last_match.a + last_match.size
        else:
            output_lines.extend(section_lines)  # If no match found, append the entire section

    # If the patch ends with [UNCHANGED], keep the rest of the file.
    # NOTE: If no [UNCHANGED] markers, deleting more than 1/3 of the file is likely accidental so we also keep the rest in that case.
    accidental_deletion = len(patch_sections) == 1 and start_idx < len(original_lines) * 2 / 3
    if patch.rstrip().endswith('[UNCHANGED]') or accidental_deletion:
        output_lines.extend(original_lines[start_idx:])

    return add_trailing_newlines(original, ''.join(output_lines))


# Main edit function

def apply_edits(response: str) -> dict[Path, tuple[str, str]]:
    modifications = {}
    for file_path_str, code_block in extract_code_blocks(response):
        file_path = Path(file_path_str).expanduser()
        file_exists = file_path.exists()
        if file_exists:
            file_data = file_path.read_text()
            modified = apply_section_edit(file_data, code_block)
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
    args = parser.parse_args()

    with open(args.original) as f:
        original_content = f.read()
    with open(args.patch) as f:
        patch_content = f.read()
    _, patch_content = extract_first_code_block(patch_content)
    edited_content = apply_section_edit(original_content, patch_content)

    print("Diff between original and edited content:")
    print_diff(original_content, edited_content, args.original)
