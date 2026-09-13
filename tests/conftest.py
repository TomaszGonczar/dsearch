"""Global test safeguards."""

import socket
from collections.abc import Iterator
from typing import NoReturn

import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: MonkeyPatch) -> Iterator[None]:
    """Make accidental network access fail before leaving the process."""

    def blocked(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("network access is forbidden in the default test suite")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket.socket, "sendto", blocked)
    yield
