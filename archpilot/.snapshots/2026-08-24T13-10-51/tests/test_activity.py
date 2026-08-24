from archpilot.activity import MAX, describe, from_blocks


def test_a_command_is_named_by_its_program():
    """The first word is the useful half; a long pipeline's flags are noise."""
    assert describe("Bash", {"command": "rg --hidden -n 'foo' src/"}) == "running rg"


def test_an_elevated_command_keeps_the_program_after_sudo():
    """"running sudo" would hide the part you actually want to know."""
    assert describe("Bash", {"command": "sudo pacman -Syu"}) == "running sudo pacman"


def test_a_command_with_no_text_still_says_something():
    assert describe("Bash", {"command": "  "}) == "running a command"


def test_file_tools_use_the_basename():
    assert describe("Read", {"file_path": "/etc/hostname"}) == "reading hostname"
    assert describe("Edit", {"file_path": "/a/b/theme.py"}) == "editing theme.py"


def test_a_trailing_slash_does_not_produce_an_empty_name():
    assert describe("Read", {"file_path": "/var/log/"}) == "reading log"


def test_search_tools_show_what_is_being_looked_for():
    assert "needle" in describe("Grep", {"pattern": "needle"})
    assert "files" in describe("Glob", {})


def test_mcp_tools_read_as_server_then_tool():
    assert describe("mcp__github__list_issues") == "github: list issues"


def test_an_unknown_tool_degrades_to_its_own_name():
    assert describe("SomeNewTool") == "some new tool"


def test_long_text_is_trimmed_to_fit_one_line():
    out = describe("Grep", {"pattern": "x" * 200})
    assert len(out) <= MAX


def test_the_last_tool_call_in_a_message_wins():
    """A message can propose several; the last one is what is running now."""
    blocks = [{"type": "text", "text": "let me look"},
              {"type": "tool_use", "name": "Read", "input": {"file_path": "/a.txt"}},
              {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]
    assert from_blocks(blocks) == "running ls"


def test_a_message_with_no_tool_calls_describes_nothing():
    assert from_blocks([{"type": "text", "text": "just talking"}]) == ""
    assert from_blocks([]) == ""
