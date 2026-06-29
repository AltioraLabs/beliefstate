"""Tests for beliefstate.call (LLMCall, LLMResponse, _make_json_safe)."""

from beliefstate.call import LLMCall, LLMResponse, _make_json_safe


class TestMakeJsonSafe:
    def test_dict(self):
        assert _make_json_safe({"a": 1}) == {"a": 1}

    def test_nested_dict(self):
        result = _make_json_safe({"a": {"b": [1, 2]}})
        assert result == {"a": {"b": [1, 2]}}

    def test_list(self):
        assert _make_json_safe([1, 2, 3]) == [1, 2, 3]

    def test_tuple(self):
        assert _make_json_safe((1, 2)) == [1, 2]

    def test_string_passthrough(self):
        assert _make_json_safe("hello") == "hello"

    def test_int_passthrough(self):
        assert _make_json_safe(42) == 42

    def test_float_passthrough(self):
        assert _make_json_safe(3.14) == 3.14

    def test_bool_passthrough(self):
        assert _make_json_safe(True) is True

    def test_none_passthrough(self):
        assert _make_json_safe(None) is None

    def test_non_serializable_converted_to_str(self):
        from datetime import datetime

        result = _make_json_safe(datetime(2024, 1, 1))
        assert isinstance(result, str)


class TestLLMCall:
    def test_basic(self):
        call = LLMCall(messages=[{"role": "user", "content": "Hi"}])
        assert len(call.messages) == 1
        assert call.kwargs == {}
        assert call.system is None
        assert call.metadata == {}

    def test_model_dump_json_safe(self):
        call = LLMCall(
            messages=[{"role": "user", "content": "Hi"}],
            kwargs={"key": object()},
        )
        data = call.model_dump()
        assert isinstance(data["kwargs"]["key"], str)

    def test_with_metadata(self):
        call = LLMCall(
            messages=[],
            metadata={"model": "gpt-4o", "temperature": 0.7},
        )
        assert call.metadata["model"] == "gpt-4o"


class TestLLMResponse:
    def test_basic(self):
        resp = LLMResponse(text="Hello", raw_response=None)
        assert resp.text == "Hello"
        assert resp.raw_response is None
        assert resp.metadata == {}

    def test_with_metadata(self):
        resp = LLMResponse(text="Hi", raw_response=None, metadata={"tokens": 10})
        assert resp.metadata["tokens"] == 10
