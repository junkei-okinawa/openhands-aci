import pytest

from openhands_aci.editor.exceptions import (
    EditorToolParameterInvalidError,
    EditorToolParameterMissingError,
    ToolError,
)


def test_tool_error():
    """Test ToolError raises with correct message."""
    with pytest.raises(ToolError) as exc_info:
        raise ToolError('A tool error occurred')
    assert str(exc_info.value) == 'A tool error occurred'


def test_editor_tool_parameter_missing_error():
    """Test EditorToolParameterMissingError for missing parameter error message."""
    command = 'str_replace'
    parameter = 'old_str'
    with pytest.raises(EditorToolParameterMissingError) as exc_info:
        raise EditorToolParameterMissingError(command, parameter)
    assert exc_info.value.command == command
    assert exc_info.value.parameter == parameter
    assert (
        exc_info.value.message
        == f'Parameter `{parameter}` is required for command: {command}.'
    )


def test_editor_tool_parameter_invalid_error_with_hint():
    """Test EditorToolParameterInvalidError with hint."""
    parameter = 'timeout'
    value = -10
    command = 'test_command'
    hint = 'Must be a positive integer.'
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        raise EditorToolParameterInvalidError(command, parameter, value, hint)
    assert exc_info.value.parameter == parameter
    assert exc_info.value.value == value
    assert exc_info.value.message == f'Invalid `{parameter}` parameter for command `{command}`: {value}. {hint}'


def test_editor_tool_parameter_invalid_error_without_hint():
    """Test EditorToolParameterInvalidError without hint."""
    parameter = 'timeout'
    command = 'test_command'
    value = -10
    with pytest.raises(EditorToolParameterInvalidError) as exc_info:
        raise EditorToolParameterInvalidError(command, parameter, value)
    assert exc_info.value.parameter == parameter
    assert exc_info.value.value == value
    assert exc_info.value.message == f'Invalid `{parameter}` parameter for command `{command}`: {value}.'
