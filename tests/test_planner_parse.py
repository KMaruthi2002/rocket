import sys
import unittest

# Importing the planner pulls in the profiler and tools packages, which need
# torch/transformers. Parsing needs none of it, so stub them when absent.
from unittest import mock

for _name in ("torch", "torch.profiler", "torch.nn", "transformers"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = mock.MagicMock()

from rocket.agents.planner import Planner


class PlannerParseTest(unittest.TestCase):
    def test_plain_object(self):
        d = Planner._parse('{"tool": "dtype_cast", "params": {"target": "bf16"}, "reasoning": "r"}')
        self.assertEqual((d.tool, d.params, d.reasoning), ("dtype_cast", {"target": "bf16"}, "r"))

    def test_trailing_prose_with_braces(self):
        d = Planner._parse('{"tool": "sdpa_attention", "params": {}} Note: params look like {x}.')
        self.assertEqual(d.tool, "sdpa_attention")

    def test_first_object_wins_over_later_alternative(self):
        text = '```json\n{"tool": "dtype_cast"}\n```\nAlternative: {"tool": "torch_compile"}'
        self.assertEqual(Planner._parse(text).tool, "dtype_cast")

    def test_null_params_become_empty_dict(self):
        self.assertEqual(Planner._parse('{"tool": "sdpa_attention", "params": null}').params, {})

    def test_missing_tool_raises_value_error(self):
        with self.assertRaises(ValueError):
            Planner._parse('{"params": {}}')

    def test_non_object_params_raise_value_error(self):
        with self.assertRaises(ValueError):
            Planner._parse('{"tool": "dtype_cast", "params": "bf16"}')


if __name__ == "__main__":
    unittest.main()
