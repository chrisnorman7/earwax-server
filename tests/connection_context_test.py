from typing import Dict
from gevent.socket import socket as GeventSocket
from earwax_server import ConnectionContext


def test_init() -> None:
    s: GeventSocket = GeventSocket()
    ctx: ConnectionContext = ConnectionContext(s, ('example.com', 1234, 0, 0))
    assert ctx.logger.name == 'example.com:1234'
    assert ctx.socket is s
    assert ctx.hostname == 'example.com'
    assert ctx.port == 1234


def test_hashability() -> None:
    ctx: ConnectionContext = ConnectionContext(
        GeventSocket(), ('example.com', 1234, 0, 0)
    )
    d: Dict[ConnectionContext, str] = {ctx: 'Testing'}
    assert d[ctx] == 'Testing'
