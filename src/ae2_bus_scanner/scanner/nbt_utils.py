from typing import Any, Dict, List, Optional

from nbt import nbt


SIDE_KEYS = ("up", "down", "north", "south", "west", "east")


def tag_value(compound: Any, key: str, default: Any = None) -> Any:
    if not isinstance(compound, nbt.TAG_Compound) or key not in compound:
        return default
    value = compound[key]
    if hasattr(value, "value"):
        return value.value
    return value


def tag_to_python(value: Any) -> Any:
    if isinstance(value, nbt.TAG_Compound):
        return {key: tag_to_python(value[key]) for key in value.keys()}
    if isinstance(value, nbt.TAG_List):
        return [tag_to_python(item) for item in value]
    if isinstance(value, (nbt.TAG_Byte_Array, nbt.TAG_Int_Array, nbt.TAG_Long_Array)):
        return list(value.value)
    if hasattr(value, "value"):
        return value.value
    return value


def detect_filter_kind(entry: Any) -> str:
    code = tag_value(entry, "#c")
    if code == "ae2:i":
        return "item"
    if code == "ae2:f":
        return "fluid"
    return "unknown"


def normalize_config_items_tag(config: Any) -> List[Dict[str, Any]]:
    if not isinstance(config, nbt.TAG_List):
        return []
    items: List[Dict[str, Any]] = []
    for slot, entry in enumerate(config):
        if not isinstance(entry, nbt.TAG_Compound):
            continue
        item_id = tag_value(entry, "id")
        if not item_id:
            continue
        item: Dict[str, Any] = {
            "id": item_id,
            "kind": detect_filter_kind(entry),
            "slot": slot,
        }
        count = tag_value(entry, "Count")
        if count is not None:
            item["count"] = count
        if "tag" in entry:
            item["tag"] = tag_to_python(entry["tag"])
        items.append(item)
    return items


def normalize_settings_tag(side_data: Any) -> Dict[str, Any]:
    if not isinstance(side_data, nbt.TAG_Compound):
        return {}
    ignored = {"id", "config", "upgrades", "patterns", "returnInv", "sendList", "gn", "outer"}
    settings: Dict[str, Any] = {}
    for key in side_data.keys():
        if key in ignored:
            continue
        settings[key] = tag_to_python(side_data[key])
    return settings


def generic_recursive_items(value: Any, path: str = "") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    py = tag_to_python(value)
    if isinstance(py, dict):
        if "id" in py and isinstance(py["id"], str):
            found.append({"path": path or "$", "item": py})
        for key, child in py.items():
            child_path = f"{path}.{key}" if path else key
            found.extend(generic_recursive_items(child, child_path))
    elif isinstance(py, list):
        for index, child in enumerate(py):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            found.extend(generic_recursive_items(child, child_path))
    return found
