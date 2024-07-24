import unittest
from ask.edit import apply_udiff_edit, apply_section_edit

original = """
import random

def generate_number():
    return random.randint(1, 100)

def is_even(number):
    return number % 2 == 0

def is_odd(number):
    return number % 2 != 0

def main():
    num = generate_number()
    print(f"Generated number: {num}")
    if is_even(num):
        print("The number is even")
    else:
        print("The number is odd")
""".lstrip()

simple_edit_patch = """
import random

def generate_number():
    return random.randint(5, 50)

[UNCHANGED]
"""

middle_edit_patch = """
import random

[UNCHANGED]

def is_even(number):
    return number % 2 == 0

def is_odd(number):
    return (number + 1) % 2 == 0

def main():
[UNCHANGED]
"""


class TestApplyEdit(unittest.TestCase):
    def test_simple_edit(self):
        expected = original.replace("return random.randint(1, 100)", "return random.randint(5, 50)")
        self.assertEqual(expected, apply_edit(original, simple_edit_patch))

    def test_edit_with_unchanged_in_middle(self):
        expected = original.replace("return number % 2 != 0", "return (number + 1) % 2 == 0")
        self.assertEqual(expected, apply_edit(original, middle_edit_patch))


if __name__ == '__main__':
    unittest.main()
