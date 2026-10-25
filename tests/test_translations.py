"""Catalog keys and defaults."""

import json
from pathlib import Path

from custom_components.philips_airpurifier_coap.const import DOMAIN


def test_translation_catalogs_and_entity_keys():
    """Keep English defaults aligned and resolve existing entity keys."""
    root = Path(__file__).parents[1] / "custom_components" / DOMAIN
    english = json.loads((root / "strings.json").read_text())
    assert english == json.loads((root / "translations/en.json").read_text())
    for path in [root / "strings.json", root / "icons.json", *(root / "translations").glob("*.json")]:
        entity = json.loads(path.read_text()).get("entity")
        if not entity:
            continue
        assert "gas_level" in entity["sensor"]
        assert "oscillation" in entity["number"]
        assert "target_temperature" in entity["number"]
        assert "gas_level" in entity["select"]["preferred_index"]["state"]
