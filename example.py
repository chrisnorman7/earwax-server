"""A basic chat server example."""

import sys
from logging import basicConfig, info

from earwax_server import ConnectionContext, Server

server: Server = Server()


@server.event
def on_connect(ctx: ConnectionContext) -> None:
    """Let everyone else know someone has arrived."""
    other: ConnectionContext
    for other in server.connections:
        if other is ctx:
            ctx.send_string('Welcome to the server.')
            ctx.send_string(
                f'Other connections: {len(server.connections) - 1}.'
            )
        else:
            other.send_string(f'New connection from {ctx.logger.name}.')


@server.event
def on_disconnect(ctx: ConnectionContext) -> None:
    """Tell everyone who has just left."""
    other: ConnectionContext
    for other in server.connections:
        other.send_string(f'{ctx.logger.name} has disconnected.')


@server.event
def on_data(ctx: ConnectionContext, data: bytes) -> None:
    """Send a message to everyone."""
    if data.decode().strip() == 'quit':
        ctx.send_string('Goodbye.')
        ctx.disconnect()
        return
    other: ConnectionContext
    name: bytes = ctx.logger.name.encode(sys.getdefaultencoding())
    sep: bytes = ': '.encode(sys.getdefaultencoding())
    message: bytes = name + sep + data
    for other in server.connections:
        other.send_bytes(message)


if __name__ == '__main__':
    basicConfig(stream=sys.stdout, level='INFO')
    info('Server starting...')
    try:
        server.run(1234)
    except KeyboardInterrupt:
        info('Server done.')
