"""Explicit native tool-call fixtures; never recover structured output from text."""

from memorias_licantropicas.contracts.model import LLMResponse


def requested_schema(tools, tool_choice=None):
    assert len(tools) == 1, "Structured test doubles require one declared output tool"
    function = tools[0]["function"]
    name = function["name"]
    assert function["parameters"]["type"] == "object"
    assert tool_choice != "none", "A tool cannot be emitted when calls are disabled"
    if isinstance(tool_choice, dict):
        assert tool_choice["function"]["name"] == name
    elif tool_choice is not None:
        assert tool_choice in {"auto", "any", "required", name}
    return name


def tool_response(payload, name="NpcSpeech", *, model="native-test-double", **usage):
    assert isinstance(payload, dict), "Fixtures supply typed arguments, not JSON text"
    return LLMResponse(
        model=model,
        tool_calls=(
            {"name": name, "args": payload, "id": "fixture-call", "type": "tool_call"},
        ),
        **usage,
    )


def respond_to_tools(payload, tools, tool_choice=None, **metadata):
    return tool_response(payload, requested_schema(tools, tool_choice), **metadata)


def invalid_tool_response(
    arguments, name="NpcSpeech", *, model="invalid-native-test-double"
):
    return LLMResponse(
        model=model,
        invalid_tool_calls=(
            {
                "name": name,
                "args": arguments,
                "id": "invalid-fixture-call",
                "type": "invalid_tool_call",
                "error": "invalid_tool_arguments",
            },
        ),
    )
