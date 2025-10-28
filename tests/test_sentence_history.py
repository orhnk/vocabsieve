from vocabsieve.ui.sentence_history import SentenceHistory


def test_sentence_history_checkpoints_and_steps():
    history = SentenceHistory(max_nodes=5)
    assert history.position() == (1, 1)

    history.checkpoint("first")
    history.checkpoint("second")
    assert history.position() == (3, 3)

    assert history.can_step(-1)
    assert history.step(-1) == "first"
    assert history.position() == (2, 3)

    assert history.can_step(1)
    assert history.step(1) == "second"
    assert history.position() == (3, 3)


def test_sentence_history_trim_keeps_latest_entries():
    history = SentenceHistory(max_nodes=3)
    history.checkpoint("one")
    history.checkpoint("two")
    history.checkpoint("three")
    history.checkpoint("four")

    # After exceeding max_nodes, we should still be at newest entry
    assert history.position() == (3, 3)
    assert history.step(-1) == "three"
    assert history.step(-1) == "two"
    assert not history.can_step(-1)
