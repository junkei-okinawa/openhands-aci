import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Literal, get_args

from openhands_aci.linter import DefaultLinter
from openhands_aci.utils.shell import run_shell_cmd

from .config import SNIPPET_CONTEXT_WINDOW
from .exceptions import (
    EditorToolParameterInvalidError,
    EditorToolParameterMissingError,
    ToolError,
)
from .prompts import DIRECTORY_CONTENT_TRUNCATED_NOTICE, FILE_CONTENT_TRUNCATED_NOTICE
from .results import CLIResult, maybe_truncate
from ..linter.base import LintResult

Command = Literal[
    'view',
    'create',
    'str_replace',
    'insert',
    'undo_edit',
    # 'jump_to_definition', TODO:
    # 'find_references' TODO:
]


class OHEditor:
    '''
    An filesystem editor tool that allows the agent to
    - view
    - create
    - navigate
    - edit files
    The tool parameters are defined by Anthropic and are not editable.

    Original implementation: https://github.com/anthropics/anthropic-quickstarts/blob/main/computer-use-demo/computer_use_demo/tools/edit.py
    '''

    TOOL_NAME = 'oh_editor'

    def __init__(self):
        self._file_history: dict[Path, list[str]] = defaultdict(list)
        self._linter = DefaultLinter()

    def __call__(
        self,
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        enable_linting: bool = False,
        **kwargs,
    ) -> CLIResult:
        _path = Path(path)
        self.validate_path(command, _path)
        if command == 'view':
            return self.view(_path, view_range)
        elif command == 'create':
            if file_text is None:
                raise EditorToolParameterMissingError(command, 'file_text')
            self.write_file(_path, file_text)
            self._file_history[_path].append(file_text)
            return CLIResult(
                path=str(_path),
                new_content=file_text,
                prev_exist=False,
                output=f'File created successfully at: {_path}',
            )
        elif command == 'str_replace':
            if old_str is None:
                raise EditorToolParameterMissingError(command, 'old_str')
            if new_str == old_str:
                raise EditorToolParameterInvalidError(
                    'new_str',
                    new_str,
                    'No replacement was performed. `new_str` and `old_str` must be different.',
                )
            return self.str_replace(_path, old_str, new_str, enable_linting, **kwargs)
        elif command == 'insert':
            if insert_line is None:
                raise EditorToolParameterMissingError(command, 'insert_line')
            if new_str is None:
                raise EditorToolParameterMissingError(command, 'new_str')
            return self.insert(_path, insert_line, new_str, enable_linting)
        elif command == 'undo_edit':
            return self.undo_edit(_path)

        raise ToolError(
            f'Unrecognized command {command}. The allowed commands for the {self.TOOL_NAME} tool are: {', '.join(get_args(Command))}'
        )

    def str_replace(
        self,
        path: Path,
        old_str: str,
        new_str: str | None,
        enable_linting: bool,
        line_numbers: list[int] | None = None,
        line_range: list[int] | None = None,
        line_all: bool = False,
        delete_lines: list[int] | None = None,
        delete_range: list[int] | None = None,
        regex: bool = False,
    ) -> CLIResult:
        '''
        Implement the str_replace command, which replaces `old_str` with `new_str` in the file content.

        The behavior of this command is controlled by several optional parameters:

        - `old_str`: (required) The string to be replaced.
          - It is expanded using expandtabs() before processing.
          - By default, the replacement is performed on the first exact match of `old_str`.
          - If `old_str` is not found, a ToolError is raised.
          - If `old_str` appears multiple times and no line-specific parameters are used, a ToolError is raised.

        - `new_str`: (optional, defaults to '') The string to replace `old_str` with.
          - It is expanded using expandtabs() before processing.
          - If not provided, `old_str` will be effectively deleted.

        - `line_numbers`: (optional, list of integers) A list of line numbers where the replacement should occur.
          - Line numbers are 1-indexed.
          - If provided, the replacement will only occur on the specified lines.
          - If a line number is out of range, it will be ignored.
          - This parameter takes precedence over `line_range` and the default single replacement behavior.
          - If used with `line_all=True`, `line_all` will be ignored.

        - `line_range`: (optional, list of two integers) A range of line numbers (inclusive) where the replacement should occur.
          - The first element is the start line, and the second is the end line.
          - Line numbers are 1-indexed.
          - If provided, the replacement will only occur on lines within the specified range.
          - This parameter takes precedence over the default single replacement behavior, but is ignored if `line_numbers` is provided.
          - If used with `line_all=True`, `line_all` will be ignored.

        - `line_all`: (optional, boolean, defaults to False) If True, all occurrences of `old_str` will be replaced.
          - If False, only the first occurrence will be replaced, unless `line_numbers` or `line_range` are provided.
          - If `line_numbers` or `line_range` are provided, this parameter is ignored.

        - `delete_lines`: (optional, list of integers) A list of line numbers to delete.
          - Line numbers are 1-indexed.
          - If provided, the specified lines will be deleted, and other replacement parameters will be ignored.
          - This parameter takes the highest precedence.

        - `delete_range`: (optional, list of two integers) A range of line numbers (inclusive) to delete.
          - The first element is the start line, and the second is the end line.
          - Line numbers are 1-indexed.
          - If provided, the specified lines will be deleted, and other replacement parameters will be ignored, except for `delete_lines`.
          - This parameter takes precedence over all other parameters except `delete_lines`.

        - `regex`: (optional, boolean, defaults to False) If True, `old_str` will be treated as a regular expression.
          - If False, `old_str` will be treated as a literal string.
          - When `regex=True` and `line_all=True`, all matching occurrences will be replaced.
          - When `regex=True` and `line_all=False`, only the first matching occurrence will be replaced.
          - When `regex=True` and `line_numbers` or `line_range` are provided, the regex replacement will be applied only on the specified lines.

        **Parameter precedence:**
        - `delete_lines` has the highest precedence. If provided, other parameters are ignored.
        - `delete_range` has the second highest precedence. If provided, other parameters except `delete_lines` are ignored.
        - `line_numbers` has the third highest precedence. If provided, `line_range` and `line_all` are ignored.
        - `line_range` has the fourth highest precedence. If provided, `line_all` is ignored.
        - `line_all` is considered only if `line_numbers` and `line_range` are not provided.
        - If none of `line_numbers`, `line_range`, `line_all`, `delete_lines`, or `delete_range` are provided, the replacement is performed on the first occurrence of `old_str`.

        **Potential issues:**
        - If `old_str` is not found in the file, a `ToolError` will be raised.
        - If `old_str` appears multiple times and no line-specific parameters are used, a `ToolError` will be raised to prevent unintended replacements.
        - When using `regex=True`, ensure that `old_str` is a valid regular expression.
        - When using `line_numbers` or `line_range`, ensure that the line numbers are within the valid range of the file.
        - When using `delete_lines` or `delete_range`, ensure that the line numbers are within the valid range of the file.

        '''
        file_content = self.read_file(path).expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ''

        if new_str is None:
            new_str = ''

        file_content_lines = file_content.split('\n')
        num_lines = len(file_content_lines)
        
        def validate_min_or_max(pattern: str, min_line: int, max_line: int, num_lines: int):
            if min_line <= 0:
                raise ToolError(f'Invalid {pattern}: {min_line}. Line numbers must be between 1 and {num_lines}.')
            if num_lines < max_line:
                raise ToolError(f'Invalid {pattern}: {max_line}. Line numbers must be between 1 and {num_lines}.')
        
        # Validate line numbers
        if line_numbers:
            validate_min_or_max('line number', min(line_numbers), max(line_numbers), num_lines)
        if line_range:
            validate_min_or_max('line range', min(line_range), max(line_range), num_lines)
            start , end = line_range
            if start > end:
                raise ToolError(f'Invalid line range: {line_range}. Start line must be less than or equal to end line.')
        if delete_lines:
            validate_min_or_max('delete lines', min(delete_lines), max(delete_lines), num_lines)
        if delete_range:
            validate_min_or_max('delete range', min(delete_range), max(delete_range), num_lines)
            start , end = delete_range
            if start > end:
                raise ToolError(f'Invalid delete range: {delete_range}. Start line must be less than or equal to end line.')

        # Delete specified line
        if delete_lines:
            delete_lines = [i - 1 for i in delete_lines]
            new_file_content_lines = [line for i, line in enumerate(file_content_lines) if not i in delete_lines]
            new_file_content = '\n'.join(new_file_content_lines)
            self.write_file(path, new_file_content)
            self._file_history[path].append(file_content)
            return CLIResult(
                output=f'The file {path} has been edited. Specified lines have been deleted.',
                prev_exist=True,
                path=str(path),
                old_content=file_content,
                new_content=new_file_content,
            )

        # Delete lines within a specified range
        if delete_range:
            start, end = delete_range
            new_file_content_lines = [line for i, line in enumerate(file_content_lines) if not (start <= i + 1 <= end)]
            new_file_content = '\n'.join(new_file_content_lines)
            self.write_file(path, new_file_content)
            self._file_history[path].append(file_content)
            return CLIResult(
                output=f'The file {path} has been edited. The specified line range was deleted.',
                prev_exist=True,
                path=str(path),
                old_content=file_content,
                new_content=new_file_content,
            )

        # If line_all is False, perform replacement on specific lines or a single occurrence
        if not line_all:
            # Replace on specific lines
            if line_numbers:
                replace_lines = [i - 1 for i in line_numbers]
                for i in replace_lines:
                    if i < len(file_content_lines):
                        if regex:
                            file_content_lines[i] = re.sub(old_str, new_str, file_content_lines[i], flags=re.DOTALL)
                        else:
                            file_content_lines[i] = file_content_lines[i].replace(old_str, new_str)
                new_file_content = '\n'.join(file_content_lines)
            # Replace within a specific line range
            elif line_range:
                start, end = line_range
                for i in range(start - 1, end):
                    if i < len(file_content_lines):
                        if regex:
                            file_content_lines[i] = re.sub(old_str, new_str, file_content_lines[i], flags=re.DOTALL)
                        else:
                            file_content_lines[i] = file_content_lines[i].replace(old_str, new_str)
                new_file_content = '\n'.join(file_content_lines)
            # Replace a single occurrence
            else:
                if regex:
                    # One-time substitution using regex
                    new_file_content = re.sub(old_str, new_str, file_content, 1)
                else:
                    # Ensure old_str exists and is unique for non-regex single replacement
                    occurrences = file_content.count(old_str)
                    if occurrences == 0:
                        raise ToolError(
                            f'No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}.'
                        )
                    if occurrences > 1:
                        # Find starting line numbers for each occurrence
                        line_numbers = []
                        start_idx = 0
                        while True:
                            idx = file_content.find(old_str, start_idx)
                            if idx == -1:
                                break
                            # Count newlines before this occurrence to get the line number
                            line_num = file_content.count('\n', 0, idx) + 1
                            line_numbers.append(line_num)
                            start_idx = idx + 1
                        raise ToolError(
                            f'No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {line_numbers}. Please ensure it is unique.'
                        )
                    new_file_content = file_content.replace(old_str, new_str)
        # If line_all is True, replace all occurrences
        else:
            if regex:
                # Replace all occurrences using regex
                new_file_content = re.sub(old_str, new_str, file_content, flags=re.DOTALL)
            else:
                # Replace all occurrences using string replace
                file_content_lines = file_content.splitlines()
                new_file_content_lines = [line.replace(old_str, new_str) for line in file_content_lines]
                new_file_content = '\n'.join(new_file_content_lines)

        # Write the new content to the file
        self.write_file(path, new_file_content)

        # Save the content to history for undo functionality
        self._file_history[path].append(file_content)

        # Create a snippet of the edited section for user feedback
        replacement_line = file_content.split(old_str)[0].count('\n')
        start_line = max(0, replacement_line - SNIPPET_CONTEXT_WINDOW)
        end_line = replacement_line + SNIPPET_CONTEXT_WINDOW + new_str.count('\n')
        snippet = '\n'.join(new_file_content.split('\n')[start_line : end_line + 1])

        # Prepare the success message
        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet, f'a snippet of {path}', start_line + 1
        )

        if enable_linting:
            # Run linting on the changes
            lint_results = self._run_linting(file_content, new_file_content, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected. Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_content,
            new_content=new_file_content,
        )

    def view(self, path: Path, view_range: list[int] | None = None) -> CLIResult:
        '''
        View the contents of a file or a directory.
        '''
        if path.is_dir():
            if view_range:
                raise EditorToolParameterInvalidError(
                    'view_range',
                    view_range,
                    'The `view_range` parameter is not allowed when `path` points to a directory.',
                )

            # First count hidden files/dirs in current directory only
            # -mindepth 1 excludes . and .. automatically
            _, hidden_stdout, _ = run_shell_cmd(
                rf"""find -L {path} -mindepth 1 -maxdepth 1 -name '.*'"""
            )
            hidden_count = (
                len(hidden_stdout.strip().split('\n')) if hidden_stdout.strip() else 0
            )

            # Then get files/dirs up to 2 levels deep, excluding hidden entries at both depth 1 and 2
            _, stdout, stderr = run_shell_cmd(
                rf"""find -L {path} -maxdepth 2 -not \( -path '{path}/\.*' -o -path '{path}/*/\.*' \) | sort""",
                truncate_notice=DIRECTORY_CONTENT_TRUNCATED_NOTICE,
            )
            if not stderr:
                msg = [
                    f"""Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n{stdout}"""
                ]
                if hidden_count > 0:
                    msg.append(
                        f'\n{hidden_count} hidden files/directories in this directory are excluded. You can use "ls -la {path}" to see them.'
                    )
                stdout = '\n'.join(msg)
            return CLIResult(
                output=stdout,
                error=stderr,
                path=str(path),
                prev_exist=True,
            )

        file_content = self.read_file(path)
        start_line = 1
        if not view_range:
            return CLIResult(
                output=self._make_output(file_content, str(path), start_line),
                path=str(path),
                prev_exist=True,
            )

        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                'It should be a list of two integers.',
            )

        file_content_lines = file_content.split('\n')
        num_lines = len(file_content_lines)
        start_line, end_line = view_range
        if start_line < 1 or start_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its first element `{start_line}` should be within the range of lines of the file: {[1, num_lines]}.',
            )

        if end_line > num_lines:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be smaller than the number of lines in the file: `{num_lines}`.',
            )

        if end_line != -1 and end_line < start_line:
            raise EditorToolParameterInvalidError(
                'view_range',
                view_range,
                f'Its second element `{end_line}` should be greater than or equal to the first element `{start_line}`.',
            )

        if end_line == -1:
            file_content = '\n'.join(file_content_lines[start_line - 1 :])
        else:
            file_content = '\n'.join(file_content_lines[start_line - 1 : end_line])
        return CLIResult(
            path=str(path),
            output=self._make_output(file_content, str(path), start_line),
            prev_exist=True,
        )

    def write_file(self, path: Path, file_text: str) -> None:
        '''
        Write the content of a file to a given path; raise a ToolError if an error occurs.
        '''
        try:
            path.write_text(file_text)
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to write to {path}') from None

    def insert(
        self, path: Path, insert_line: int, new_str: str, enable_linting: bool
    ) -> CLIResult:
        '''
        Implement the insert command, which inserts new_str at the specified line in the file content.
        '''
        try:
            file_text = self.read_file(path)
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to read {path}') from None

        file_text = file_text.expandtabs()
        new_str = new_str.expandtabs()

        file_text_lines = file_text.split('\n')
        num_lines = len(file_text_lines)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorToolParameterInvalidError(
                'insert_line',
                insert_line,
                f'It should be within the range of lines of the file: {[0, num_lines]}',
            )

        new_str_lines = new_str.split('\n')
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_CONTEXT_WINDOW) : insert_line]
            + new_str_lines
            + file_text_lines[
                insert_line : min(num_lines, insert_line + SNIPPET_CONTEXT_WINDOW)
            ]
        )
        new_file_text = '\n'.join(new_file_text_lines)
        snippet = '\n'.join(snippet_lines)

        self.write_file(path, new_file_text)
        self._file_history[path].append(file_text)

        success_message = f'The file {path} has been edited. '
        success_message += self._make_output(
            snippet,
            'a snippet of the edited file',
            max(1, insert_line - SNIPPET_CONTEXT_WINDOW + 1),
        )

        if enable_linting:
            # Run linting on the changes
            lint_results = self._run_linting(file_text, new_file_text, path)
            success_message += '\n' + lint_results + '\n'

        success_message += 'Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary.'
        return CLIResult(
            output=success_message,
            prev_exist=True,
            path=str(path),
            old_content=file_text,
            new_content=new_file_text,
        )

    def validate_path(self, command: Command, path: Path) -> None:
        '''
        Check that the path/command combination is valid.
        '''
        # Check if its an absolute path
        if not path.is_absolute():
            suggested_path = Path.cwd() / path
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path should be an absolute path, starting with `/`. Maybe you meant {suggested_path}?',
            )
        # Check if path and command are compatible
        if command == 'create' and path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'File already exists at: {path}. Cannot overwrite files using command `create`.',
            )
        if command != 'create' and not path.exists():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} does not exist. Please provide a valid path.',
            )
        if command != 'view' and path.is_dir():
            raise EditorToolParameterInvalidError(
                'path',
                path,
                f'The path {path} is a directory and only the `view` command can be used on directories.',
            )

    def undo_edit(self, path: Path) -> CLIResult:
        '''
        Implement the undo_edit command.
        '''
        if not self._file_history[path]:
            raise ToolError(f'No edit history found for {path}.')

        current_text = self.read_file(path).expandtabs()
        old_text = self._file_history[path].pop()
        self.write_file(path, old_text)

        return CLIResult(
            output=f'Last edit to {path} undone successfully. {self._make_output(old_text, str(path))}',
            path=str(path),
            prev_exist=True,
            old_content=current_text,
            new_content=old_text,
        )

    def read_file(self, path: Path) -> str:
        '''
        Read the content of a file from a given path; raise a ToolError if an error occurs.
        '''
        try:
            return path.read_text()
        except Exception as e:
            raise ToolError(f'Ran into {e} while trying to read {path}') from None

    def _make_output(
        self,
        snippet_content: str,
        snippet_description: str,
        start_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        '''
        Generate output for the CLI based on the content of a code snippet.
        '''
        snippet_content = maybe_truncate(
            snippet_content, truncate_notice=FILE_CONTENT_TRUNCATED_NOTICE
        )
        if expand_tabs:
            snippet_content = snippet_content.expandtabs()

        snippet_content = '\n'.join(
            [
                f'{i + start_line:6}\t{line}'
                for i, line in enumerate(snippet_content.split('\n'))
            ]
        )
        return (
            f"""Here's the result of running `cat -n` on {snippet_description}:\n"""
            + snippet_content
            + '\n'
        )

    def _run_linting(self, old_content: str, new_content: str, path: Path) -> str:
        '''
        Run linting on file changes and return formatted results.
        '''
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create paths with exact filenames in temp directory
            temp_old = Path(temp_dir) / f'old.{path.name}'
            temp_new = Path(temp_dir) / f'new.{path.name}'

            # Write content to temporary files
            temp_old.write_text(old_content)
            temp_new.write_text(new_content)

            # Run linting on the changes
            results = self._linter.lint_file_diff(str(temp_old), str(temp_new))

            if not results:
                return 'No linting issues found in the changes.'

            # Format results
            output = ['Linting issues found in the changes:']
            for result in results:
                output.append(
                    f'- Line {result.line}, Column {result.column}: {result.message}'
                )
            return '\n'.join(output) + '\n'
