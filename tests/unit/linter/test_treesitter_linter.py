from openhands_aci.linter import DefaultLinter, LintResult
from openhands_aci.linter.impl.treesitter import TreesitterBasicLinter


def test_syntax_error_py_file(syntax_error_py_file):
    linter = TreesitterBasicLinter()
    result = linter.lint(syntax_error_py_file)
    print(result)
    assert isinstance(result, list) and len(result) == 1
    assert result[0] == LintResult(
        file=syntax_error_py_file,
        line=5,
        column=5,
        message='Syntax error',
    )

    assert (
        result[0].visualize()
        == (
            '2|    def foo():\n'
            '3|        print("Hello, World!")\n'
            '4|    print("Wrong indent")\n'
            '\033[91m5|    foo(\033[0m\n'  # color red
            '      ^ ERROR HERE: Syntax error\n'
            '6|'
        )
    )
    print(result[0].visualize())

    general_linter = DefaultLinter()
    general_result = general_linter.lint(syntax_error_py_file)
    # NOTE: general linter returns different result
    # because it uses flake8 first, which is different from treesitter
    assert general_result != result


def test_simple_correct_ruby_file(simple_correct_ruby_file):
    linter = TreesitterBasicLinter()
    result = linter.lint(simple_correct_ruby_file)
    assert isinstance(result, list) and len(result) == 0

    # Test that the general linter also returns the same result
    general_linter = DefaultLinter()
    general_result = general_linter.lint(simple_correct_ruby_file)
    assert general_result == result


def test_simple_incorrect_ruby_file(simple_incorrect_ruby_file):
    linter = TreesitterBasicLinter()
    result = linter.lint(simple_incorrect_ruby_file)
    print(result)
    assert isinstance(result, list) and len(result) == 2
    assert result[0] == LintResult(
        file=simple_incorrect_ruby_file,
        line=1,
        column=1,
        message='Syntax error',
    )
    print(result[0].visualize())
    assert (
        result[0].visualize()
        == (
            '\033[91m1|def foo():\033[0m\n'  # color red
            '  ^ ERROR HERE: Syntax error\n'
            '2|    print("Hello, World!")\n'
            '3|foo()'
        )
    )
    assert result[1] == LintResult(
        file=simple_incorrect_ruby_file,
        line=1,
        column=10,
        message='Syntax error',
    )
    print(result[1].visualize())
    assert (
        result[1].visualize()
        == (
            '\033[91m1|def foo():\033[0m\n'  # color red
            '           ^ ERROR HERE: Syntax error\n'
            '2|    print("Hello, World!")\n'
            '3|foo()'
        )
    )

    # Test that the general linter also returns the same result
    general_linter = DefaultLinter()
    general_result = general_linter.lint(simple_incorrect_ruby_file)
    assert general_result == result


def test_parenthesis_incorrect_ruby_file(parenthesis_incorrect_ruby_file):
    linter = TreesitterBasicLinter()
    result = linter.lint(parenthesis_incorrect_ruby_file)
    print(result)
    assert isinstance(result, list) and len(result) == 1
    assert result[0] == LintResult(
        file=parenthesis_incorrect_ruby_file,
        line=1,
        column=1,
        message='Syntax error',
    )
    print(result[0].visualize())
    assert result[0].visualize() == (
        '\033[91m1|def print_hello_world()\033[0m\n'
        '  ^ ERROR HERE: Syntax error\n'
        "2|    puts 'Hello World'"
    )

    # Test that the general linter also returns the same result
    general_linter = DefaultLinter()
    general_result = general_linter.lint(parenthesis_incorrect_ruby_file)
    assert general_result == result


def test_treesitter_with_unsupported_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.unknown"
    test_file.write_text("some content")
    result = linter.lint(str(test_file))
    assert result == []

def test_treesitter_with_missing_node(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    test_file.write_text("def test(:\n    pass")  # Missing parenthesis
    result = linter.lint(str(test_file))
    assert len(result) > 0
    assert result[0].message == 'Missing node'

def test_treesitter_with_empty_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    test_file.write_text("")
    result = linter.lint(str(test_file))
    assert result == []

def test_treesitter_with_invalid_encoding(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    test_file.write_bytes(b'\x80\x81\x82')  # Invalid UTF-8
    result = linter.lint(str(test_file))
    assert len(result) == 1
    assert result[0].message == 'Invalid file encoding: File must be valid UTF-8'
    assert result[0].line == 1
    assert result[0].column == 1

def test_treesitter_with_parser_error(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Write a file that will definitely cause a syntax error
    test_file.write_text("def test[]\n")  # Invalid function definition
    result = linter.lint(str(test_file))
    assert len(result) > 0
    assert result[0].message == 'Syntax error'

def test_treesitter_with_severe_parser_error(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Create a file that will cause parser to fail
    test_file.write_text("]]][[[")  # Invalid Python syntax
    result = linter.lint(str(test_file))
    assert len(result) == 1
    assert result[0].message == 'Syntax error'
    assert result[0].line == 1
    assert result[0].column == 1

def test_treesitter_with_mixed_encoding(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Mix valid UTF-8 with invalid bytes
    test_file.write_bytes(b"def test():\n    print('hello')\x80\x81\x82")
    result = linter.lint(str(test_file))
    assert len(result) == 1
    assert 'Invalid file encoding' in result[0].message

def test_treesitter_with_binary_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Create a binary file
    test_file.write_bytes(bytes(range(256)))
    result = linter.lint(str(test_file))
    assert len(result) == 1
    assert 'Invalid file encoding' in result[0].message

def test_treesitter_with_unknown_language(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.xyz"
    test_file.write_text("some content")
    result = linter.lint(str(test_file))
    assert result == []

def test_treesitter_with_complex_syntax(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # 複雑な構文を含むコード
    test_file.write_text("""
def test():
    try:
        yield from range(10)
    except Exception as e:
        async with context() as ctx:
            await ctx.do_something()
"""
    )
    result = linter.lint(str(test_file))
    assert result == []

def test_treesitter_with_multiple_errors(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # 複数のエラーを含むコード
    test_file.write_text("""
def test(
    print("unclosed parenthesis"
if True
    print("no colon")
"""
    )
    result = linter.lint(str(test_file))
    assert len(result) > 1
    assert all('Syntax error' in r.message for r in result)

def test_treesitter_with_null_byte(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    test_file.write_bytes(b"print('hello')\x00print('world')")
    result = linter.lint(str(test_file))
    assert len(result) > 0

def test_treesitter_with_large_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Create a large file with valid syntax
    test_file.write_text("x = 1\n" * 10000)
    result = linter.lint(str(test_file))
    assert result == []

def test_treesitter_with_missing_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "nonexistent.py"
    result = linter.lint(str(test_file))
    assert isinstance(result, list)
    assert len(result) == 0  # Should return empty list for missing files

def test_treesitter_with_inaccessible_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")
    
    # Make file inaccessible by changing permissions
    test_file.chmod(0o000)
    
    try:
        result = linter.lint(str(test_file))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].message == 'File is not accessible: Permission denied'
        assert result[0].line == 1
        assert result[0].column == 1
    finally:
        # Restore permissions to allow cleanup
        test_file.chmod(0o644)

def test_treesitter_with_permission_error_directory(tmp_path):
    linter = TreesitterBasicLinter()
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    test_file = test_dir / "test.py"
    test_file.write_text("print('hello')")
    
    # Make directory inaccessible
    test_dir.chmod(0o000)
    
    try:
        result = linter.lint(str(test_file))
        assert isinstance(result, list)
        assert len(result) == 1
        assert 'Permission denied' in result[0].message
    finally:
        # Restore permissions to allow cleanup
        test_dir.chmod(0o755)

def test_treesitter_with_corrupted_file(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Create a file with partial UTF-8 sequence
    test_file.write_bytes(b"def test():\n\xe2")
    result = linter.lint(str(test_file))
    assert len(result) == 1
    assert 'Invalid file encoding' in result[0].message

def test_treesitter_with_invalid_syntax_multiline(tmp_path):
    linter = TreesitterBasicLinter()
    test_file = tmp_path / "test.py"
    # Multiple syntax errors in different lines
    test_file.write_text("""
def test(:  # Missing parenthesis
    if True  # Missing colon
        print(x  # Missing parenthesis
""")
    result = linter.lint(str(test_file))
    assert len(result) > 2  # Should detect multiple errors
    assert all(r.message in ['Syntax error', 'Missing node'] for r in result)
