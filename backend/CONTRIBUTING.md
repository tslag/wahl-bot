# Contributing

This document describes the project's contribution guidelines focused on code comments, docstrings, and developer workflow. We follow the Google Python style for docstrings and prefer concise, rationale-first inline comments.

## Goals

- Make public APIs self-documenting (clear docstrings, types).
- Ensure comments explain *why*, not *what*.
- Enforce style using automated checks in CI / pre-commit.

## Docstring style

We use Google-style docstrings. Write docstrings for modules, public classes, and public functions.

Function example (Google style):

```py
def add(a: int, b: int) -> int:
    """Add two integers.

    Args:
        a: First integer.
        b: Second integer.

    Returns:
        The sum of `a` and `b`.

    Raises:
        ValueError: If inputs are invalid.

    Example:
        >>> add(1, 2)
        3
    """
    return a + b
```

Class example:

```py
class Processor:
    """Process documents into embeddings.

    Attributes:
        model_name: Name of the embedding model.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
```

## Inline comment rules

- Use inline comments sparingly; explain rationale, trade-offs, or non-obvious constraints.
- Prefer `# NOTE:` for design decisions and `# TODO: <ticket>` for tracked work.
- Avoid comments that repeat code (e.g., `# increment i` for `i += 1`).

## Configuring pre-commit for Python development

Use pre-commit for ensuring code quality and consistent formatting amongst all developers. You can read more about pre-commit [here](https://pre-commit.com/).

Please run the following commands to configure pre-commit in the virtual environment.

```powershell
pip install --upgrade pre-commit black pylint
pre-commit install
pre-commit run
```
