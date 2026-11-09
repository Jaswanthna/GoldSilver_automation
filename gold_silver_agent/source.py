from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
from soupsieve import SelectorSyntaxError


class MessageSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MessageSource:
    url: str
    response_format: str
    fields: dict[str, dict[str, str]]
    template: str
    compare_fields: tuple[str, ...]


def load_message_source(path: str | Path) -> MessageSource:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MessageSourceError(f"Unable to read message source configuration: {exc}") from exc

    if not isinstance(config, dict):
        raise MessageSourceError("Message source configuration must be a JSON object")
    url = config.get("url")
    response_format = config.get("format")
    fields = config.get("fields")
    template = config.get("template")
    compare_fields = config.get("compare_fields")
    parsed = urlparse(url) if isinstance(url, str) else None
    if (
        parsed is None
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise MessageSourceError("Source URL must be an HTTPS URL without credentials or a fragment")
    if not isinstance(response_format, str) or response_format not in {"html", "json"}:
        raise MessageSourceError("Source format must be 'html' or 'json'")
    if not isinstance(fields, dict) or not fields:
        raise MessageSourceError("Source fields must be a non-empty object")
    if not isinstance(template, str) or not template.strip():
        raise MessageSourceError("Source template must be a non-empty string")
    if compare_fields is None:
        compare_fields = list(fields)
    if (
        not isinstance(compare_fields, list)
        or not compare_fields
        or any(not isinstance(name, str) or name not in fields for name in compare_fields)
    ):
        raise MessageSourceError("Source compare_fields must be a non-empty list of configured field names")

    for name, spec in fields.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise MessageSourceError(f"Invalid source field name: {name!r}")
        if not isinstance(spec, dict):
            raise MessageSourceError(f"Source field {name!r} must be an object")
        key = "selector" if response_format == "html" else "path"
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise MessageSourceError(f"Source field {name!r} requires a non-empty {key!r}")
        pattern = spec.get("pattern")
        if pattern is not None:
            if response_format != "html":
                raise MessageSourceError(f"Pattern is only supported for HTML source field {name!r}")
            if not isinstance(pattern, str):
                raise MessageSourceError(f"Pattern for source field {name!r} must be a string")
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise MessageSourceError(f"Invalid pattern for source field {name!r}: {exc}") from exc
            if compiled.groups != 1:
                raise MessageSourceError(
                    f"Pattern for source field {name!r} must contain exactly one capture group"
                )

    placeholder_pattern = r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
    placeholders = set(re.findall(placeholder_pattern, template))
    template_without_placeholders = re.sub(placeholder_pattern, "", template)
    if "{{" in template_without_placeholders or "}}" in template_without_placeholders:
        raise MessageSourceError("Template contains an invalid placeholder")
    unknown = placeholders - fields.keys()
    if unknown:
        raise MessageSourceError("Template references undefined fields: " + ", ".join(sorted(unknown)))

    return MessageSource(url, response_format, fields, template, tuple(compare_fields))


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise MessageSourceError("JSON field paths must use JSON Pointer syntax, starting with '/'")

    current = value
    for encoded_part in pointer[1:].split("/"):
        part = encoded_part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise KeyError(part)
        except (KeyError, IndexError, ValueError):
            raise MessageSourceError(f"Could not find configured JSON field at {pointer!r}") from None
    if isinstance(current, (dict, list)) or current is None:
        raise MessageSourceError(f"Configured JSON field at {pointer!r} is not a scalar value")
    return str(current).strip()


def _extract_fields(source: MessageSource, content: str) -> dict[str, str]:
    if source.response_format == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise MessageSourceError(f"Source returned invalid JSON: {exc}") from exc
        values = {name: _json_pointer(data, spec["path"]) for name, spec in source.fields.items()}
    else:
        soup = BeautifulSoup(content, "html.parser")
        values = {}
        for name, spec in source.fields.items():
            try:
                element = soup.select_one(spec["selector"])
            except SelectorSyntaxError as exc:
                raise MessageSourceError(f"Invalid CSS selector for source field {name!r}: {exc}") from exc
            if element is None:
                raise MessageSourceError(f"Could not find configured HTML field {name!r}")
            value = element.get_text(" ", strip=True)
            pattern = spec.get("pattern")
            if pattern:
                match = re.search(pattern, value)
                if match is None:
                    raise MessageSourceError(f"Could not parse configured HTML field {name!r}")
                value = match.group(1).strip()
            values[name] = value

    missing = [name for name, value in values.items() if not value]
    if missing:
        raise MessageSourceError("Source returned empty required fields: " + ", ".join(missing))
    return values


def fetch_message_data(source: MessageSource) -> tuple[str, dict[str, str]]:
    parsed = urlparse(source.url)
    try:
        response = requests.get(
            source.url,
            headers={"User-Agent": "TelegramDataNotifier/1.0"},
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise MessageSourceError("Unable to fetch configured message source; check the URL and network") from None

    if 300 <= response.status_code < 400:
        raise MessageSourceError("Configured source redirected the request; refusing redirected content")
    if not 200 <= response.status_code < 300:
        raise MessageSourceError(f"Configured source returned HTTP {response.status_code}")
    if urlparse(response.url).hostname != parsed.hostname:
        raise MessageSourceError("Configured source response came from an unexpected host")

    content_type = response.headers.get("Content-Type", "").lower()
    if source.response_format == "html" and "html" not in content_type:
        raise MessageSourceError("Configured source response was not HTML")
    if source.response_format == "json" and "json" not in content_type:
        raise MessageSourceError("Configured source response was not JSON")

    values = _extract_fields(source, response.text)
    message = re.sub(
        r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}",
        lambda match: values[match.group(1)],
        source.template,
    )
    return message, {name: values[name] for name in source.compare_fields}


def fetch_message(source: MessageSource) -> str:
    message, _ = fetch_message_data(source)
    return message
