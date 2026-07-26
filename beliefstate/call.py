from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


class LLMCall(BaseModel):
    """Universal representation of an LLM API call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[dict[str, Any]]
    kwargs: dict[str, Any] = Field(default_factory=dict)
    system: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        data["kwargs"] = _make_json_safe(data.get("kwargs", {}))
        return data


class LLMResponse(BaseModel):
    """Universal representation of an LLM API response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str
    raw_response: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
