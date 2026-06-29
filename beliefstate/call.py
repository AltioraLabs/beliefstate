from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


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

    messages: List[Dict[str, Any]]
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    system: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        data["kwargs"] = _make_json_safe(data.get("kwargs", {}))
        return data


class LLMResponse(BaseModel):
    """Universal representation of an LLM API response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str
    raw_response: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)
