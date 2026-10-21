"""Catalog keys, placeholders, and defaults."""

import json
import string
from pathlib import Path

from custom_components.philips_airpurifier_coap.const import DOMAIN


def test_translation_keys_and_turkish_placeholders():
    """Resolve existing entity keys and keep English/Turkish catalogs aligned."""
    root = Path(__file__).parents[1] / "custom_components" / DOMAIN
    english = json.loads((root / "strings.json").read_text())
    turkish = json.loads((root / "translations/tr.json").read_text())
    assert english == json.loads((root / "translations/en.json").read_text())

    def compare(left, right):
        if isinstance(left, dict):
            assert left.keys() == right.keys()
            for key in left:
                compare(left[key], right[key])
        else:
            formatter = string.Formatter()
            assert {f for _, f, _, _ in formatter.parse(left) if f} == {f for _, f, _, _ in formatter.parse(right) if f}

    compare(english, turkish)
    for path in [root / "strings.json", root / "icons.json", *(root / "translations").glob("*.json")]:
        entity = json.loads(path.read_text()).get("entity")
        if not entity:
            continue
        assert "gas_level" in entity["sensor"]
        assert "oscillation" in entity["number"]
        assert "target_temperature" in entity["number"]
        assert "gas_level" in entity["select"]["preferred_index"]["state"]
    assert turkish["entity"]["number"]["target_humidity"]["name"] == "Hedef nem"
