from earwax_server import Server


def test_init() -> None:
    s = Server()
    assert isinstance(s._events, dict)
    assert s.connections == []
    assert s.stream_server is None
