"""Device state machine (plan section 1): IDLE -> LISTENING -> THINKING -> SPEAKING."""

from __future__ import annotations

from common.messages import State

ALLOWED: dict[State, set[State]] = {
    State.IDLE: {State.LISTENING},
    State.LISTENING: {State.THINKING, State.IDLE},  # IDLE on timeout
    State.THINKING: {State.SPEAKING, State.IDLE},
    State.SPEAKING: {State.IDLE, State.LISTENING},  # LISTENING on barge-in
}


class StateMachine:
    def __init__(self) -> None:
        self._state = State.IDLE

    @property
    def state(self) -> State:
        return self._state

    def transition(self, target: State) -> State:
        if target not in ALLOWED[self._state]:
            raise ValueError(f"illegal transition {self._state} -> {target}")
        self._state = target
        return self._state
