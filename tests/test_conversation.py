from gateway.conversation.history import SYSTEM_PROMPT, Conversation


def test_system_prompt_is_always_first():
    """Prefix caching only works if the system prompt never moves."""
    conversation = Conversation()
    conversation.add_user("oi")
    conversation.add_assistant("oi!")
    prompt = conversation.prompt()
    assert prompt[0].role == "system"
    assert prompt[0].content == SYSTEM_PROMPT


def test_history_is_trimmed():
    conversation = Conversation(max_turns=2)
    for i in range(5):
        conversation.add_user(f"pergunta {i}")
        conversation.add_assistant(f"resposta {i}")
    turns = conversation.prompt()[1:]
    assert len(turns) == 4
    assert turns[0].content == "pergunta 3"
