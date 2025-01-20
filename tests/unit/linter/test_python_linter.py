from openhands_aci.linter import DefaultLinter, LintResult
from openhands_aci.linter.impl.python import (
    PythonLinter,
    flake_lint,
    python_compile_lint,
)


def test_wrongly_indented_py_file(wrongly_indented_py_file):
    # Test Python linter
    linter = PythonLinter()
    assert '.py' in linter.supported_extensions
    result = linter.lint(wrongly_indented_py_file)
    print(result)
    assert isinstance(result, list) and len(result) == 1
    assert result[0] == LintResult(
        file=wrongly_indented_py_file,
        line=2,
        column=5,
        message='E999 IndentationError: unexpected indent',
    )
    print(result[0].visualize())
    assert result[0].visualize() == (
        '1|\n'
        '\033[91m2|    def foo():\033[0m\n'
        '      ^ ERROR HERE: E999 IndentationError: unexpected indent\n'
        '3|            print("Hello, World!")\n'
        '4|'
    )

    # General linter should have same result as Python linter
    # bc it uses PythonLinter under the hood
    general_linter = DefaultLinter()
    assert '.py' in general_linter.supported_extensions
    result = general_linter.lint(wrongly_indented_py_file)
    assert result == linter.lint(wrongly_indented_py_file)

    # Test flake8_lint
    assert result == flake_lint(wrongly_indented_py_file)

    # Test python_compile_lint
    compile_result = python_compile_lint(wrongly_indented_py_file)
    assert isinstance(compile_result, list) and len(compile_result) == 1
    assert compile_result[0] == LintResult(
        file=wrongly_indented_py_file, line=2, column=4, message='unexpected indent'
    )


def test_simple_correct_py_file(simple_correct_py_file):
    linter = PythonLinter()
    assert '.py' in linter.supported_extensions
    result = linter.lint(simple_correct_py_file)
    assert result == []

    general_linter = DefaultLinter()
    assert '.py' in general_linter.supported_extensions
    result = general_linter.lint(simple_correct_py_file)
    assert result == linter.lint(simple_correct_py_file)

    # Test python_compile_lint
    compile_result = python_compile_lint(simple_correct_py_file)
    assert compile_result == []

    # Test flake_lint
    flake_result = flake_lint(simple_correct_py_file)
    assert flake_result == []


def test_simple_correct_py_func_def(simple_correct_py_func_def):
    linter = PythonLinter()
    result = linter.lint(simple_correct_py_func_def)
    assert result == []

    general_linter = DefaultLinter()
    assert '.py' in general_linter.supported_extensions
    result = general_linter.lint(simple_correct_py_func_def)
    assert result == linter.lint(simple_correct_py_func_def)

    # Test flake_lint
    assert result == flake_lint(simple_correct_py_func_def)

    # Test python_compile_lint
    compile_result = python_compile_lint(simple_correct_py_func_def)
    assert compile_result == []


def test_python_linter_with_invalid_flake8_output(simple_correct_py_file, monkeypatch):
    def mock_run_shell_cmd(*args, **kwargs):
        return 0, "invalid:format:output:without:line:number"
    
    monkeypatch.setattr('openhands_aci.linter.impl.python.run_shell_cmd', mock_run_shell_cmd)
    
    result = flake_lint(simple_correct_py_file)
    assert result == []


def test_python_linter_with_missing_column(simple_correct_py_file, monkeypatch):
    def mock_run_shell_cmd(*args, **kwargs):
        return 0, f"{simple_correct_py_file}:1:invalid_column:error message"
    
    monkeypatch.setattr('openhands_aci.linter.impl.python.run_shell_cmd', mock_run_shell_cmd)
    
    result = flake_lint(simple_correct_py_file)
    assert len(result) == 1
    assert result[0].column == 1
    assert "invalid_column error message" in result[0].message

def test_python_linter_with_flake8_not_found(simple_correct_py_file, monkeypatch):
    def mock_run_shell_cmd(*args, **kwargs):
        raise FileNotFoundError("flake8 not found")
    
    monkeypatch.setattr('openhands_aci.linter.impl.python.run_shell_cmd', mock_run_shell_cmd)
    
    result = flake_lint(simple_correct_py_file)
    assert result == []

def test_compile_lint_with_code(tmp_path):
    linter = PythonLinter()
    test_file = tmp_path / "test.py"
    valid_code = "print('hello')"
    result = linter.compile_lint(str(test_file), valid_code)
    assert result == []

def test_compile_lint_with_invalid_code(tmp_path):
    linter = PythonLinter()
    test_file = tmp_path / "test.py"
    invalid_code = "print('hello'"  # Missing parenthesis
    result = linter.compile_lint(str(test_file), invalid_code)
    assert len(result) == 1
    assert 'SyntaxError:' in result[0].message
