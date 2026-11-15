# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""PWM / buzzer adapter for `audiodev.ToneOutput`."""

from collections.abc import Callable
from typing import Any

from audiodev import AudioSession, ToneOutput

class PWMToneOutput(ToneOutput):
    """Tone output around a PWM pin or an object with `play` / `stop`."""

    def __init__(
        self,
        pwm: Any,
        *,
        session: AudioSession | None = None,
        power: Callable[[bool], Any] | None = None,
    ) -> None: ...
    @property
    def pwm(self) -> Any: ...

def tone_out(
    pwm: Any,
    *,
    session: AudioSession | None = None,
    power: Callable[[bool], Any] | None = None,
) -> PWMToneOutput:
    """Build a `PWMToneOutput` around `pwm` (instance or factory)."""
