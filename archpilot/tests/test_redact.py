"""Secret scrubbing for replayed/displayed text (privacy pass)."""

from archpilot import redact
from archpilot.session import replay_text


def test_key_value_pairs_scrubbed():
    # Name + separator stay (readable), only the value goes.
    assert redact.scrub("password=hunter2 here") == "password=…redacted… here"
    assert redact.scrub("api_key: ABCDEF rest") == "api_key: …redacted… rest"
    assert redact.scrub('token="abc123" ok') == "token=…redacted… ok"


def test_bare_tokens_scrubbed():
    assert "sk-" not in redact.scrub("key sk-abcdefgh1234 done")
    assert "ghp_" not in redact.scrub("tok ghp_abcdefgh1234 done")
    assert "AKIA" not in redact.scrub("id AKIAIOSFODNN7EXAMPLE done")
    assert "LLM_" not in redact.scrub("k LLM_2159816524957487_x done")


def test_pem_blocks_scrubbed():
    pem = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    assert redact.scrub(f"a {pem} b") == "a …redacted… b"


def test_plain_text_untouched_and_idempotent():
    text = "how do I write a for loop in fish?"
    assert redact.scrub(text) == text
    once = redact.scrub("password=hunter2")
    assert redact.scrub(once) == once


def test_url_queries_stripped():
    assert redact.scrub_url_query("page - https://x/y?token=abc&n=1") == (
        "page - https://x/y?…")
    assert redact.scrub_url_query("no query here") == "no query here"


def test_replay_scrubs_secrets():
    turns = [{"prompt": "my password=hunter2 ok?", "answer": "use sk-abcdefgh1234",
              "engine": "claude"}]
    out = replay_text(turns)
    assert "hunter2" not in out and "sk-abcdefgh" not in out
    assert "…redacted…" in out
