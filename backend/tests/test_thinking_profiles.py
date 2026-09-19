import os
import unittest

from app.gpt.thinking_profiles import (
    apply_thinking_to_kwargs,
    normalize_thinking,
    resolve_want_thinking,
    suggest_thinking_profile,
)


class TestThinkingProfiles(unittest.TestCase):
    def test_flash_suggests_toggleable_off(self):
        p = suggest_thinking_profile("qwen3.7-flash-2026-07-15")
        self.assertEqual(p["capability"], "toggleable")
        self.assertEqual(p["mode"], "off")
        self.assertEqual(p["strategy"], "dashscope_enable_thinking")

    def test_max_preview_forced_on(self):
        p = suggest_thinking_profile("qwen3.7-max-preview")
        self.assertEqual(p["capability"], "forced_on")
        self.assertEqual(p["strategy"], "forced_on")
        self.assertTrue(resolve_want_thinking(p))

    def test_apply_dashscope_off(self):
        thinking = suggest_thinking_profile("qwen3.7-flash")
        kw = apply_thinking_to_kwargs({"model": "x", "messages": []}, thinking)
        self.assertEqual(kw["extra_body"]["enable_thinking"], False)

    def test_apply_forced_on_skips_extra_body(self):
        thinking = suggest_thinking_profile("qwen3.7-max-preview")
        kw = apply_thinking_to_kwargs({"model": "x", "messages": []}, thinking)
        self.assertNotIn("extra_body", kw)

    def test_inherit_respects_env(self):
        thinking = {
            "mode": "inherit",
            "capability": "toggleable",
            "strategy": "dashscope_enable_thinking",
        }
        os.environ["LLM_ENABLE_THINKING"] = "true"
        self.assertTrue(resolve_want_thinking(thinking))
        os.environ["LLM_ENABLE_THINKING"] = "false"
        self.assertFalse(resolve_want_thinking(thinking))

    def test_normalize_merges_stored(self):
        stored = {"thinking": {"mode": "on", "capability": "toggleable", "strategy": "dashscope_enable_thinking"}}
        out = normalize_thinking(stored, model_name="qwen3.7-flash")
        self.assertEqual(out["mode"], "on")
        self.assertEqual(out["strategy"], "dashscope_enable_thinking")


if __name__ == "__main__":
    unittest.main()
