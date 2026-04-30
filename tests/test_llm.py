"""Tests for llm.py — routing, subprocess handling, LiteLLM fallback."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import LLMError, call


class TestCall:
    def test_routes_slash_model_to_litellm(self):
        with patch("llm._litellm", return_value="ok") as mock_litellm:
            with patch("llm._claude_cli") as mock_cli:
                result = call("prompt", "openai/gpt-4o")
        mock_litellm.assert_called_once()
        mock_cli.assert_not_called()
        assert result == "ok"

    def test_routes_plain_model_to_claude_cli(self):
        with patch("llm._claude_cli", return_value="ok") as mock_cli:
            with patch("llm._litellm") as mock_litellm:
                result = call("prompt", "sonnet")
        mock_cli.assert_called_once()
        mock_litellm.assert_not_called()
        assert result == "ok"

    def test_routes_opus_to_claude_cli(self):
        with patch("llm._claude_cli", return_value="reply") as mock_cli:
            call("prompt", "opus")
        mock_cli.assert_called_once()


class TestClaudeCli:
    def _run(self, stdout="output", returncode=0, stderr=""):
        mock_result = MagicMock()
        mock_result.stdout = stdout
        mock_result.returncode = returncode
        mock_result.stderr = stderr
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            from llm import _claude_cli
            result = _claude_cli("prompt", "sonnet", timeout=30)
        return result, mock_run

    def test_returns_stripped_stdout(self):
        result, _ = self._run(stdout="  hello world  ")
        assert result == "hello world"

    def test_raises_llmerror_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "auth error"
        with patch("subprocess.run", return_value=mock_result):
            from llm import _claude_cli
            with pytest.raises(LLMError, match="auth error"):
                _claude_cli("prompt", "sonnet", timeout=30)

    def test_includes_model_flag_for_named_model(self):
        mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            from llm import _claude_cli
            _claude_cli("prompt", "opus", timeout=30)
        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        # alias "opus" is resolved to a dated ID like "claude-opus-4-7"
        assert any("opus" in arg for arg in cmd)

    def test_skips_model_flag_for_default(self):
        mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            from llm import _claude_cli
            _claude_cli("prompt", "default", timeout=30)
        cmd = mock_run.call_args[0][0]
        assert "--model" not in cmd


class TestLiteLLM:
    def test_raises_llmerror_when_not_installed(self):
        with patch.dict("sys.modules", {"litellm": None}):
            from llm import _litellm
            with pytest.raises((LLMError, ImportError)):
                _litellm("prompt", "openai/gpt-4o")

    def test_returns_content_on_success(self):
        mock_completion = MagicMock()
        mock_completion.return_value.choices[0].message.content = "  reply text  "
        with patch.dict("sys.modules", {"litellm": MagicMock(completion=mock_completion)}):
            from llm import _litellm
            result = _litellm("prompt", "openai/gpt-4o")
        assert result == "reply text"
