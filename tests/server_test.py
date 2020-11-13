from earwax_server import Server


def test_init() -> None:
    s = Server()
    assert isinstance(s.events, dict)
    assert s.sockets == []
    assert s.server is None
