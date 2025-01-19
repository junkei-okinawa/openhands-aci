class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        self.message = message

    def __str__(self):
         return self.message


class EditorToolParameterMissingError(ToolError):
    """Raised when a required parameter is missing for a tool command."""

    def __init__(self, command, parameter):
        self.command = command
        self.parameter = parameter
        super().__init__(f'Parameter `{parameter}` is required for command: {command}.')


class EditorToolParameterInvalidError(ToolError):
    """Raised when a parameter is invalid for a tool command."""

    def __init__(self, command, parameter, value, hint=None):
        self.command = command
        self.parameter = parameter
        self.value = value
        if hint:
            super().__init__(f'Invalid `{parameter}` parameter for command `{command}`: {value}. {hint}')
        else:
            super().__init__(f'Invalid `{parameter}` parameter for command `{command}`: {value}.')
