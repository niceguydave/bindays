"""Shared pytest configuration.

Key principle from *Speed Up Your Django Tests*: the suite should pass in
"aeroplane mode". We enforce that by wrapping every test in a requests-mock
``Mocker``, so any real outbound HTTP request raises ``NoMockAddress`` instead of
silently hitting the network. Tests that exercise HTTP register their expected
responses on the per-test ``requests_mock`` fixture, which stacks on top of this.
"""

import pytest
import requests_mock as rm


@pytest.fixture(autouse=True)
def _block_unexpected_network():
    with rm.Mocker():
        yield
