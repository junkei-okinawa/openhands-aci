from typing import Dict, List, Union, Literal, Any, TypedDict

class ItemType(TypedDict):
    type: Literal["integer"]

class PropertyType(TypedDict, total=False):
        description: str
        type: Literal["string", "integer", "array", "boolean", "object"]
        enum: List[str]
        items: ItemType

class ParametersType(TypedDict):
    type: Literal["object"]
    properties: Dict[str, PropertyType]
    required: List[str]


STR_REPLACE_EDITOR_DESCRIPTION: Literal = """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* The `new_str` parameter should contain the edited lines that should replace the `old_str`

Notes for using the `delete` command:
*  The `delete_lines` parameter should contain the line numbers to delete.
*  The `start` and `end` parameters should contain the range of the lines to delete.
"""

PARAMETERS: ParametersType = {
    'type': 'object',
    'properties': {
        'command': {
            'description': 'The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`, `delete`.',
            'enum': ['view', 'create', 'str_replace', 'insert', 'undo_edit', 'delete'],
            'type': 'string',
        },
        'path': {
            'description': 'Absolute path to file or directory, e.g. `/workspace/file.py` or `/workspace`.',
            'type': 'string',
        },
        'file_text': {
            'description': 'Required parameter of `create` command, with the content of the file to be created.',
            'type': 'string',
        },
        'old_str': {
            'description': 'Required parameter of `str_replace` command containing the string in `path` to replace.',
            'type': 'string',
        },
        'new_str': {
            'description': 'Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.',
            'type': 'string',
        },
        'insert_line': {
            'description': 'Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.',
            'type': 'integer',
        },
        'delete_lines': {
            'description': 'Optional parameter of `delete` command. A list of line numbers to delete.',
                'type': 'array',
            'items': {'type': 'integer'},
        },
        'start': {
            'description': 'Optional parameter of `delete` command.  The start line number of the range to delete. Should be used with `end` parameter.',
            'type': 'integer',
        },
            'end': {
            'description': 'Optional parameter of `delete` command. The end line number of the range to delete. Should be used with `start` parameter.',
            'type': 'integer',
        },
        'view_range': {
            'description': 'Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
        'line_numbers': {
            'description': 'Optional parameter of `str_replace` command. A list of line numbers where the replacement should occur.',
            'type': 'array',
            'items': {'type': 'integer'},
        },
        'line_all': {
            'description': 'Optional parameter of `str_replace` command. If True, all occurrences of `old_str` will be replaced.',
            'type': 'boolean',
            },
        'regex': {
            'description': 'Optional parameter of `str_replace` command. If True, `old_str` will be treated as a regular expression.',
            'type': 'boolean',
        },
    },
    'required': ['command', 'path'],
}