"""Provides the Server class."""

from logging import Logger, getLogger
from sys import getdefaultencoding
from typing import Callable, Dict, List, Optional, Tuple, Union

from attr import Factory, attrib, attrs
from gevent.server import StreamServer
from gevent.socket import socket as GeventSocket

default_encoding: str = getdefaultencoding()
AddressTuple = Tuple[str, int, int, int]
EventHandlerType = Callable[..., Optional[bool]]

EVENT_HANDLED: bool = True
EVENT_UNHANDLED = None


class EventNameError(Exception):
    """There was a problem with an event name."""


@attrs(auto_attribs=True, hash=True)
class ConnectionContext:
    """A context for holding connection information.

    An instances of this class is created every time a new connection is made
    to a :class:`Server` instance. As such, contexts are used a lot when
    dispatching events.
    """

    socket: GeventSocket
    address: AddressTuple

    hostname: str = attrib(init=False)

    @hostname.default
    def get_hostname(instance: 'ConnectionContext') -> str:
        """Get the hostname from :attr:`instance.address <ConnectionContext.address>`.

        :param instance: The instance to get the hostname from.
        """
        return instance.address[0]

    port: int = attrib(init=False)

    @port.default
    def get_port(instance: 'ConnectionContext') -> int:
        """Get the port from :attr:`instance.address <ConnectionContext.address>`.

        :param instance: The instance to get the port from.
        """
        return instance.address[1]

    logger: Logger = attrib(init=False, repr=False)

    @logger.default
    def get_logger(instance: 'ConnectionContext') -> Logger:
        """Construct a logger using :attr:`instance.address <ServerContext.address>`.

        :ivar instance: The context the logger should be created for.
        """
        return getLogger(f'{instance.hostname}:{instance.port}')

    def send_string(self, string: str) -> None:
        """Used to send a string to :attr:`self.socket <ConnectionContext.socket>`.

        The string is automatically encoded to a bytes-like object, and "\r\n"
        is appended.

        :param string: The string to send (minus the end of line terminator).

            This value must *not* be an unencoded string.
        """
        string += '\r\n'
        self.socket.sendall(string.encode())

    def send_bytes(
        self, string: bytes, encoding: Optional[str] = None
    ) -> None:
        """Send a bytes-like object to :attr:`self.socket <ConnectionContext.socket>`.

        The string will have "\r\n" appended to it.

        :param string: The bytes-like object to send.

            This value must have already been encoded.

        :param encoding: The value to use for encoding the line terminator.

            If not specified, the system default encoding will be used.
        """
        if encoding is None:
            encoding = default_encoding
        terminator: bytes = '\r\n'.encode(encoding)
        self.socket.sendall(string + terminator)

    def send_raw(self, data: bytes) -> None:
        """Send raw data to :attr:`self.socket <ConnectionContext.socket>`.

        :param data: The data to send.
        """
        self.socket.sendall(data)

    def disconnect(self) -> None:
        """Disconnect the underlying socket."""
        self.socket.close()


@attrs(auto_attribs=True)
class Server:
    """A server instance.

    By attaching event handlers to instances of this class, you can build
    servers with very little code.

    :ivar connections: Every context that is connected to this server.

    :ivar stream_server: The underlying gevent server.
    """

    connections: List[ConnectionContext] = attrib(
        default=Factory(list), init=False, repr=False
    )

    stream_server: Optional[StreamServer] = attrib(default=None, init=False)

    _events: Dict[str, List[EventHandlerType]] = attrib(
        default=Factory(dict), init=False, repr=False
    )

    def __attrs_post_init__(self) -> None:
        """Add some events."""
        name: str
        for func in [
            self.on_block, self.on_connect, self.on_disconnect, self.on_data
        ]:
            name = func.__name__
            self.register_event_type(name)
            self.event(func)  # type: ignore[arg-type]

    def register_event_type(self, name: str) -> str:
        """Register a new event type.

        The name of the new event type will be returned.

        If the name already exists, ``EventNameError`` will be raised.

        :ivar name: The name of the new type.
        """
        if name in self._events:
            raise EventNameError(name)
        self._events[name] = []
        return name

    def dispatch_event(self, name: str, *args, **kwargs) -> None:
        """Dispatch an event.

        If the given name has not been registered with the
        :meth:`Server.register_event_type` method, then ``EventNameError`` will
        be raised.

        :ivar name: The name of the event type to dispatch.

        :ivar args: The positional arguments to be passed to the event
            handlers.

        :ivar kwargs: The keyword arguments to pass to the event handlers.
        """
        if name not in self._events:
            raise EventNameError(name)
        for handler in self._events[name]:
            value: Optional[bool] = handler(*args, **kwargs)
            if value is EVENT_HANDLED:
                break

    def event(self, value: Union[EventHandlerType, str]) -> Union[
        EventHandlerType, Callable[[EventHandlerType], EventHandlerType]
    ]:
        """Register a new event.

        The new event handler will be put at the beginning of the event
        handlers list, thus allowing newer event handlers to override older
        ones.

        When the :meth:`Server.dispatch_event` is used, the handlers list will
        be iterated over, and each handler executed.

        If a handler returns ``EVENT_HANDLED``, execution ends.

        If the provided event name (see below) is not in :attr:`self.events
        <Server.events>`, then ``EventNameError`` will be raised.

        :ivar value: Either the name of the event type this handler should
        listen to, or the event handler itself.

            If ``value`` is a string, then it will be considered the name of
            the event type, and a callable will be returned so this method can
            be used as a decorator.

            If ``value`` is a callable, then it is assumed to be the handler
            function, and its ``__name__`` attribute is used as the name. In
            this case, the handler function is returned directly.
        """
        _name: Optional[str] = None

        def inner(func: EventHandlerType) -> EventHandlerType:
            name: str = _name or func.__name__
            if name not in self._events:
                raise EventNameError(name)
            self._events[name].insert(0, func)
            return func
        if isinstance(value, str):
            _name = value
            return inner
        else:
            return inner(value)

    def can_connect(self, ctx: ConnectionContext) -> bool:
        """Return ``True`` if the provided address can connect, ``False`` otherwise.

        :ivar ctx: The context that is trying to connect.
        """
        return True

    def handle(
        self, socket: GeventSocket,
        address: AddressTuple
    ) -> None:
        """Handles opening new connections.

        :param socket: The socket that has just connected.

        :param address: The address of the new conection.
        """
        ctx: ConnectionContext = ConnectionContext(socket, address)
        if not self.can_connect(ctx):
            return self.dispatch_event('on_block', ctx)
        self.dispatch_event('on_connect', ctx)
        self.connections.append(ctx)
        f = socket.makefile(mode='rb')
        while not socket.closed:
            line: bytes = f.readline()
            if not line:
                break
            self.dispatch_event('on_data', ctx, line)
        f.close()
        self.connections.remove(ctx)
        self.dispatch_event('on_disconnect', ctx)

    def run(self, port: int, host: str = '', **kwargs) -> None:
        """Start the server running.

        Set :attr:`self.server <Server.server>` to a instance of
        ``gevent.server.StreamServer``, and call its ``serve_forever`` method.

        All extra keyword arguments are passed to the constructor of
        ``StreamServer``.

        :param port: The port to listen on.

        :param host: The address to bind to.
        """
        self.stream_server = StreamServer((host, port), handle=self.handle)
        self.stream_server.serve_forever()

    def on_block(self, ctx: ConnectionContext) -> None:
        """An event which is dispatched when an address has been blocked.

        :ivar socket: The socket that has been blocked.

        :ivar address: The address that has been blocked.
        """
        ctx.logger.info('Connection blocked.')

    def on_connect(self, ctx: ConnectionContext) -> None:
        """An event that is dispatched when a new connection is established.

        By the time this event is dispatched, it has already been established
        by the :meth:`Server.can_connect` method that this address is allowed
        to connect.

        :ivar socket: The socket that has connected.

        :ivar address: The address that ``socket`` has connected from.
        """
        ctx.logger.info('Connection established.')

    def on_disconnect(self, ctx: ConnectionContext) -> None:
        """An event that is dispatched when a connection is closed.

        :ivar ctx: The context that is disconnecting.
        """
        ctx.logger.info('Disconnected.')

    def on_data(self, ctx: ConnectionContext, data: bytes) -> None:
        """An event that fires when some data is received over a connection.

        :ivar ctx: The originating connection context.

        :ivar data: The data which has been received.

            This value will be unchanged from when it was received. As such, no
            decoding will have yet been performed, hence why a bytes object is
            passed, rather than a string.
        """
        pass
