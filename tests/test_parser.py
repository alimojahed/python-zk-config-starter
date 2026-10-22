"""Unit tests for the properties-file parser."""
import pytest

from zk_config_starter.exceptions import ZkConfigParseError
from zk_config_starter.parser import parse_properties


class TestParseProperties:
    def test_simple_equals(self) -> None:
        assert parse_properties("key=value") == {"key": "value"}

    def test_simple_colon(self) -> None:
        assert parse_properties("key:value") == {"key": "value"}

    def test_prefers_first_separator(self) -> None:
        # '=' before ':' → split on '='
        assert parse_properties("k=v:extra") == {"k": "v:extra"}

    def test_colon_before_equals(self) -> None:
        assert parse_properties("k:v=extra") == {"k": "v=extra"}

    def test_blank_lines_ignored(self) -> None:
        text = "\n\nkey=value\n\n"
        assert parse_properties(text) == {"key": "value"}

    def test_hash_comment_ignored(self) -> None:
        text = "# this is a comment\nkey=value"
        assert parse_properties(text) == {"key": "value"}

    def test_exclamation_comment_ignored(self) -> None:
        text = "! another comment\nkey=value"
        assert parse_properties(text) == {"key": "value"}

    def test_whitespace_stripped_from_key_and_value(self) -> None:
        assert parse_properties("  key  =  value  ") == {"key": "value"}

    def test_empty_value_is_allowed(self) -> None:
        assert parse_properties("key=") == {"key": ""}

    def test_multiple_properties(self) -> None:
        text = "db.host=localhost\ndb.port=5432\napp.env=production"
        assert parse_properties(text) == {
            "db.host": "localhost",
            "db.port": "5432",
            "app.env": "production",
        }

    def test_empty_string_returns_empty_dict(self) -> None:
        assert parse_properties("") == {}

    def test_only_comments_returns_empty_dict(self) -> None:
        assert parse_properties("# comment\n! another") == {}

    def test_no_separator_raises(self) -> None:
        with pytest.raises(ZkConfigParseError, match="no '=' or ':'"):
            parse_properties("this_has_no_separator")

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ZkConfigParseError, match="empty key"):
            parse_properties("=value")

    def test_duplicate_key_last_wins(self) -> None:
        text = "k=first\nk=second"
        assert parse_properties(text) == {"k": "second"}

    def test_unicode_values(self) -> None:
        assert parse_properties("greeting=こんにちは") == {"greeting": "こんにちは"}

    def test_strict_equals_mode(self) -> None:
        assert parse_properties("key=value", separators=("=",)) == {
            "key": "value"
        }

    def test_strict_equals_mode_rejects_colon(self) -> None:
        with pytest.raises(ZkConfigParseError, match="no '='"):
            parse_properties("key:value", separators=("=",))

    def test_default_separators_remain_backward_compatible(self) -> None:
        assert parse_properties("key:value") == {"key": "value"}

    @pytest.mark.parametrize("separators", [(), ("",)])
    def test_invalid_separator_configuration(self, separators: tuple) -> None:
        with pytest.raises(ValueError):
            parse_properties("key=value", separators=separators)
