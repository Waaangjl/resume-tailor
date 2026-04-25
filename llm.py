"""LLM backend — routes to claude -p or LiteLLM based on model string."""

import subprocess


class LLMError(RuntimeError):
    pass


def call(prompt: str, model: str, timeout: int = 600) -> str:
    """Send a prompt to the configured LLM and return the text response."""
    if "/" in model:
        return _litellm(prompt, model)
    return _claude_cli(prompt, model, timeout)


def _claude_cli(prompt: str, model: str, timeout: int) -> str:
    cmd = ["claude", "-p", "--output-format", "text"]
    if model.lower() not in ("claude", "default"):
        cmd += ["--model", model]
    result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise LLMError(f"claude -p error:\n{result.stderr.strip()}")
    return result.stdout.strip()


def _litellm(prompt: str, model: str) -> str:
    try:
        from litellm import completion
    except ImportError as e:
        raise LLMError("LiteLLM not installed: pip install litellm") from e
    resp = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8192,
    )
    return resp.choices[0].message.content.strip()
