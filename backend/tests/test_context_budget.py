from apps.designer_studio.context_budget import trim_chat_history


def test_trim_chat_history_limits_turns():
    history = [{"role": "user", "content": f"msg-{i}"} for i in range(30)]
    trimmed = trim_chat_history(history)
    assert len(trimmed) <= 12
