from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path


STATE_FILE = Path(__file__).resolve().parents[1] / ".last_prices.json"


class PriceStateError(RuntimeError):
    pass


def load_price_state(path: Path = STATE_FILE) -> tuple[str, dict[str, str]] | None:
    try:
        contents = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PriceStateError(f"Unable to read saved price state: {exc}") from exc

    try:
        state = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise PriceStateError(f"Saved price state is invalid JSON: {exc}") from exc
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("source"), str)
        or not isinstance(state.get("values"), dict)
        or not state["values"]
        or any(not isinstance(key, str) or not isinstance(value, str) for key, value in state["values"].items())
    ):
        raise PriceStateError("Saved price state has an invalid structure")
    return state["source"], state["values"]


def save_price_state(source: str, values: dict[str, str], path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps({"source": source, "values": values}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    except OSError as exc:
        raise PriceStateError(f"Unable to save price state: {exc}") from exc
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def prices_changed(previous: dict[str, str], current: dict[str, str]) -> bool:
    if previous.keys() != current.keys():
        return True
    return any(_normalized_value(previous[key]) != _normalized_value(value) for key, value in current.items())


def _normalized_value(value: str) -> str:
    normalized_text = " ".join(value.split())
    try:
        number = Decimal(normalized_text.replace(",", ""))
    except InvalidOperation:
        return normalized_text
    if not number.is_finite():
        return normalized_text
    return format(number.normalize(), "f")
