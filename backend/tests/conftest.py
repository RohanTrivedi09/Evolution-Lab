from __future__ import annotations

import pytest

from app.models import Weights


@pytest.fixture
def weights() -> Weights:
    return Weights()


@pytest.fixture
def unit_weights() -> Weights:
    """Every violation costs 1, so counts and total cost are directly comparable."""
    return Weights(hard=1, soft=1, gaps=1, fragmentation=1)
