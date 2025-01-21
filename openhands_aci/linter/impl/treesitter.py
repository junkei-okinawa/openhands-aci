import os
import warnings
from typing import Union
from pathlib import Path

from grep_ast import TreeContext, filename_to_lang
from grep_ast.parsers import PARSERS
from tree_sitter_languages import get_parser

from ..base import BaseLinter, LintResult

# tree_sitter is throwing a FutureWarning
warnings.simplefilter('ignore', category=FutureWarning)


def tree_context(fname, code, line_nums):
    context = TreeContext(
        fname,
        code,
        color=False,
        line_number=True,
        child_context=False,
        last_line=False,
        margin=0,
        mark_lois=True,
        loi_pad=3,
        # header_max=30,
        show_top_of_file_parent_scope=False,
    )
    line_nums = set(line_nums)
    context.add_lines_of_interest(line_nums)
    context.add_context()
    output = context.format()
    return output


def traverse_tree(node):
    """Traverses the tree to find errors."""
    errors = []
    if node.type == 'ERROR' or node.is_missing:
        line_no = node.start_point[0] + 1
        col_no = node.start_point[1] + 1
        error_type = 'Missing node' if node.is_missing else 'Syntax error'
        errors.append((line_no, col_no, error_type))

    for child in node.children:
        errors += traverse_tree(child)

    return errors


class TreesitterBasicLinter(BaseLinter):
    @property
    def supported_extensions(self) -> list[str]:
        return list(PARSERS.keys())

    def _check_file_access(self, path: Path) -> Union[None, LintResult]:
        """Check file accessibility and return error result if not accessible."""
        try:
            if not path.exists():
                return None
            
            # Check if any parent directory is not accessible
            current = path
            while current != current.parent:
                if not os.access(current.parent, os.X_OK):
                    return LintResult(
                        file=str(path),
                        line=1,
                        column=1,
                        message='File is not accessible: Permission denied'
                    )
                current = current.parent

            if not os.access(path, os.R_OK):
                return LintResult(
                    file=str(path),
                    line=1,
                    column=1,
                    message='File is not accessible: Permission denied'
                )
            return None
        except (OSError, PermissionError):
            return LintResult(
                file=str(path),
                line=1,
                column=1,
                message='File is not accessible: Permission denied'
            )

    def lint(self, file_path: str) -> list[LintResult]:
        """Use tree-sitter to look for syntax errors, display them with tree context."""
        path = Path(file_path)
        
        # Check file accessibility
        access_error = self._check_file_access(path)
        if access_error:
            return [access_error]
        if not path.exists():
            return []

        lang = filename_to_lang(file_path)
        if not lang:
            return []
            
        parser = get_parser(lang)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except UnicodeDecodeError:
            return [
                LintResult(
                    file=file_path,
                    line=1,
                    column=1,
                    message='Invalid file encoding: File must be valid UTF-8'
                )
            ]
        except (FileNotFoundError, PermissionError, IOError) as e:
            return [
                LintResult(
                    file=file_path,
                    line=1,
                    column=1,
                    message='File is not accessible: Permission denied'
                )
            ]

        try:
            tree = parser.parse(bytes(code, 'utf-8'))
        except Exception as e:
            return [
                LintResult(
                    file=file_path,
                    line=1,
                    column=1,
                    message='Syntax error: Invalid syntax'
                )
            ]

        errors = traverse_tree(tree.root_node)
        if not errors:
            return []

        # Convert all parser errors to 'Syntax error'
        return [
            LintResult(
                file=file_path,
                line=int(line),
                column=int(col),
                message='Syntax error' if 'error' in error_details.lower() else error_details,
            )
            for line, col, error_details in errors
        ]
