import pytest

from common.messages import State
from device.state import StateMachine


def test_happy_path():
    sm = StateMachine()
    assert sm.state is State.IDLE
    for target in (State.LISTENING, State.THINKING, State.SPEAKING, State.IDLE):
        assert sm.transition(target) is target


def test_barge_in():
    sm = StateMachine()
    sm.transition(State.LISTENING)
    sm.transition(State.THINKING)
    sm.transition(State.SPEAKING)
    assert sm.transition(State.LISTENING) is State.LISTENING


def test_illegal_transition():
    sm = StateMachine()
    with pytest.raises(ValueError):
        sm.transition(State.SPEAKING)
