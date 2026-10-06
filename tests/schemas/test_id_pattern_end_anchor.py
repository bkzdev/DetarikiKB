"""共有ID形式は行末ではなく文字列の完全な終端で判定する。"""

import json
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas"
LEGACY_PATTERN = r"^[A-Z][A-Z0-9_]*$"
STRICT_PATTERN = r"^[A-Z][A-Z0-9_]*(?![\s\S])"


def _patterns(value):
    if isinstance(value, dict):
        if "pattern" in value:
            yield value["pattern"]
        for child in value.values():
            yield from _patterns(child)
    elif isinstance(value, list):
        for child in value:
            yield from _patterns(child)


def test_shared_id_patterns_require_true_end_of_string():
    patterns = [
        pattern
        for path in SCHEMAS_DIR.glob("*.schema.json")
        if path.stat().st_size > 0  # 未実装のplaceholder schemaは空ファイル
        for pattern in _patterns(json.loads(path.read_text(encoding="utf-8")))
    ]
    assert LEGACY_PATTERN not in patterns
    assert STRICT_PATTERN in patterns

    validator = Draft7Validator({"type": "string", "pattern": STRICT_PATTERN})
    for value in ("A", "PUBLIC_TEST_001"):
        assert validator.is_valid(value)
    for value in (
        "PUBLIC_TEST\n",
        "PUBLIC_TEST\r",
        "PUBLIC_TEST\r\n",
        "PUBLIC_TEST\u2028",
        "PUBLIC_TEST\u2029",
    ):
        assert not validator.is_valid(value)
