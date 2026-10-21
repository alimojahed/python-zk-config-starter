"""Parser for Java-style ``.properties`` text blobs.

Supports:
- ``key=value`` and ``key:value`` separators
- ``#`` and ``!`` comment lines
- Blank lines (ignored)
- Leading/trailing whitespace trimmed from both key and value
- Keys may not be empty

Not supported (minimal implementation):
- Multi-line continuation with backslash
- Unicode escape sequences (\\uXXXX)
"""
from typing import Dict, Sequence

from .exceptions import ZkConfigParseError


def parse_properties(
    text: str,
    *,
    separators: Sequence[str] = ("=", ":"),
) -> Dict[str, str]:
    """Parse a properties-file text blob into a ``{key: value}`` dict.

    Args:
        text: The raw text content of the znode.
        separators: Allowed key/value separators. The earliest separator in
            each line is used. Defaults to ``("=", ":")`` for compatibility.

    Returns:
        A dictionary of parsed key/value pairs.

    Raises:
        ZkConfigParseError: If a non-comment, non-blank line contains no
            ``=`` or ``:`` separator.
    """
    if not separators or any(
        not isinstance(item, str) or not item for item in separators
    ):
        raise ValueError(
            "separators must contain at least one non-empty string"
        )

    result: Dict[str, str] = {}

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line[0] in ("#", "!"):
            continue

        # Find the earliest configured separator.
        positions = [
            (position, separator)
            for separator in separators
            for position in [line.find(separator)]
            if position != -1
        ]
        if not positions:
            expected = " or ".join(repr(item) for item in separators)
            raise ZkConfigParseError(
                f"Line {lineno}: no {expected} separator found: {raw_line!r}"
            )

        sep_pos, separator = min(positions, key=lambda item: item[0])

        key = line[:sep_pos].strip()
        value = line[sep_pos + len(separator):].strip()

        if not key:
            raise ZkConfigParseError(
                f"Line {lineno}: empty key found: {raw_line!r}"
            )

        result[key] = value

    return result
