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
from typing import Dict

from .exceptions import ZkConfigParseError


def parse_properties(text: str) -> Dict[str, str]:
    """Parse a properties-file text blob into a ``{key: value}`` dict.

    Args:
        text: The raw text content of the znode.

    Returns:
        A dictionary of parsed key/value pairs.

    Raises:
        ZkConfigParseError: If a non-comment, non-blank line contains no
            ``=`` or ``:`` separator.
    """
    result: Dict[str, str] = {}

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line[0] in ("#", "!"):
            continue

        # Find separator: first '=' or ':', whichever comes first
        eq_pos = line.find("=")
        colon_pos = line.find(":")

        if eq_pos == -1 and colon_pos == -1:
            raise ZkConfigParseError(
                f"Line {lineno}: no '=' or ':' separator found: {raw_line!r}"
            )

        if eq_pos == -1:
            sep_pos = colon_pos
        elif colon_pos == -1:
            sep_pos = eq_pos
        else:
            sep_pos = min(eq_pos, colon_pos)

        key = line[:sep_pos].strip()
        value = line[sep_pos + 1:].strip()

        if not key:
            raise ZkConfigParseError(
                f"Line {lineno}: empty key found: {raw_line!r}"
            )

        result[key] = value

    return result
