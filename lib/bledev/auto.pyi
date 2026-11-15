# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
from . import UnsupportedError as UnsupportedError
from _typeshed import Incomplete

BACKENDS: Incomplete

def backend_name(): ...
def adapter(backend=None, **kwargs): ...
