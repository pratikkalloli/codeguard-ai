"""Tests for fenced, generic, and prose-mixed Python extraction."""

import unittest

from codeguard.input_processing import NO_CODE_MESSAGE, extract_response


class InputProcessingTests(unittest.TestCase):
    def test_fenced_python_is_extracted_and_prose_preserved(self) -> None:
        result = extract_response(
            "Here is the answer.\n```python\ndef square(n):\n    return n * n\n```\nIt squares n."
        )
        self.assertEqual(result.code_blocks, ["def square(n):\n    return n * n"])
        self.assertIn("Here is the answer.", result.explanation)
        self.assertIn("It squares n.", result.explanation)

    def test_generic_fence_requires_valid_python(self) -> None:
        result = extract_response("``\ndef square(n):\n    return n * n\n``")
        self.assertEqual(result.code_blocks, ["def square(n):\n    return n * n"])

    def test_unfenced_python_is_extracted(self) -> None:
        result = extract_response("def square(n):\n    return n * n")
        self.assertEqual(result.code_blocks, ["def square(n):\n    return n * n"])

    def test_explanation_and_unfenced_python_are_separated(self) -> None:
        result = extract_response(
            "Here is the solution:\n\ndef square(n):\n    return n * n\n\nThis function returns the square of n."
        )
        self.assertEqual(result.code_blocks, ["def square(n):\n    return n * n"])
        self.assertIn("Here is the solution:", result.explanation)
        self.assertIn("This function returns the square of n.", result.explanation)

    def test_multiple_code_blocks_preserve_order(self) -> None:
        result = extract_response(
            "```python\nimport math\n```\nThen:\n```\nclass Box:\n    pass\n```"
        )
        self.assertEqual(result.code_blocks, ["import math", "class Box:\n    pass"])

    def test_invalid_python_fence_is_not_returned_as_code(self) -> None:
        result = extract_response("```python\ndef broken(:\n    pass\n```")
        self.assertEqual(result.code_blocks, [])
        self.assertIn("def broken(:", result.explanation)

    def test_empty_response_is_handled(self) -> None:
        self.assertEqual(extract_response(" \n ").code_blocks, [])
        self.assertEqual(extract_response("").explanation, "")
        self.assertIn("No Python code", NO_CODE_MESSAGE)

    def test_non_python_response_is_preserved(self) -> None:
        response = "The answer is 42.\n```javascript\nconst answer = 42;\n```"
        result = extract_response(response)
        self.assertEqual(result.code_blocks, [])
        self.assertIn("The answer is 42.", result.explanation)
        self.assertIn("javascript", result.explanation)

    def test_imports_functions_classes_and_normal_statements_parse(self) -> None:
        source = (
            "from pathlib import Path\n\n"
            "class Squares:\n"
            "    def values(self, items):\n"
            "        if not items:\n"
            "            return []\n"
            "        return [item * item for item in items]\n"
        )
        self.assertEqual(extract_response(source).code_blocks, [source.rstrip()])


if __name__ == "__main__":
    unittest.main()
