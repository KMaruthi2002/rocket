import unittest

from rocket.replay import replay_accepted


class Wrapped:
    def __init__(self, inner):
        self.inner = inner


def fake_compile(model, tokenizer, **_):
    return Wrapped(model), tokenizer, {"applied": True}


def fake_pad(model, tokenizer, *, multiple=128, **_):
    model.pad = multiple
    return model, tokenizer, {"applied": True}


class ReplayAcceptedTest(unittest.TestCase):
    TOOLBOX = {"torch_compile": fake_compile, "input_padding": fake_pad}

    def test_returned_model_is_carried_forward(self):
        base = type("M", (), {})()
        history = [{"tool": "torch_compile", "params": {}, "accepted": True}]
        model, _ = replay_accepted(self.TOOLBOX, base, "tok", history)
        self.assertIsInstance(model, Wrapped)
        self.assertIs(model.inner, base)

    def test_rejected_entries_are_skipped_and_order_kept(self):
        base = type("M", (), {})()
        history = [
            {"tool": "input_padding", "params": {"multiple": 64}, "accepted": False},
            {"tool": "torch_compile", "params": {}, "accepted": True},
            {"tool": "input_padding", "params": {"multiple": 256}, "accepted": True},
        ]
        model, tok = replay_accepted(self.TOOLBOX, base, "tok", history)
        self.assertEqual(tok, "tok")
        self.assertIsInstance(model, Wrapped)
        self.assertEqual(model.pad, 256)
        self.assertFalse(hasattr(base, "pad"))

    def test_empty_history_returns_inputs(self):
        model, tok = replay_accepted(self.TOOLBOX, "m", "t", [])
        self.assertEqual((model, tok), ("m", "t"))


if __name__ == "__main__":
    unittest.main()
