"""Provides the Server class."""

from typing import Callable, Dict, List, Optional, Tuple, Union

from attr import Factory, attrib, attrs
from gevent.server import StreamServer
from gevent.socket import socket as GeventSocket

AddressTuple = Tuple[str, int, int, int]
EventHandlerType = Callable[..., Optional[bool]]

EVENT_HANDLED: bool = True
EVENT_UNHANDLED = None


class EventNameError(Exception):
    """There was a problem with an event name."""


class EventTypes:
    """The possible event types for the :class:`Server` class.

    Internally, all values are simple strings, so you can feel free to define
    your own event types.
    """

    on_block: str = 'on_block'
    on_connect: str = 'on_connect'
    on_disconnect: str = 'on_disconnect'
    on_line: str = 'on_line'


@attrs(auto_attribs=True)
class Server:
    """A server instance."""

    sockets: List[GeventSocket] = attrib(
        default=Factory(list), init=False, repr=False
    )
    events: Dict[str, List[EventHandlerType]] = attrib(
        default=Factory(dict), init=False, repr=False
    )
    server: Optional[StreamServer] = attrib(default=None, init=False)

    def __attrs_post_init__(self) -> None:
        """Add some events."""
        event_type: str
        for event_type in [
            EventTypes.on_connect, EventTypes.on_disconnect, EventTypes.on_line
        ]:
            self.register_event_type(event_type)

    def register_event_type(self, name: str) -> str:
        """Register a new event type.

        The name of the new event type will be returned.

        If the name already exists, ``EventNameError`` will be raised.

        :ivar name: The name of the new type.
        """
        if name in self.events:
            raise EventNameError(name)
        self.events[name] = []
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
        if name not in self.events:
            raise EventNameError(name)
        for handler in self.events[name]:
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
            if name not in self.events:
                raise EventNameError(name)
            self.events[name].insert(0, func)
            return func
        if isinstance(value, str):
            _name = value
            return inner
        else:
            return inner(value)

    def can_connect(self, address: AddressTuple) -> bool:
        """Return ``True`` if the provided address can connect, ``False`` otherwise.

        :ivar address: The address that is trying to connect.
        """
        return True

    def handle(
        self, socket: GeventSocket,
        address: AddressTuple
    ) -> None:
        if not self.can_connect(address):
            return self.dispatch_event(EventTypes.on_block, address)
        self.dispatch_event(EventTypes.on_connect)
        f = socket.makefile(mode='rb')
        while True:
            line = f.readline()
            if not line:
                self.dispatch_event(EventTypes.on_disconnect, address)
                break
            self.dispatch_event(EventTypes.on_line, socket, address, line)
        f.close()

    def run(self, port: int, host: str = '', **kwargs) -> None:
        """Start the server running.

        Set :attr:`self.server <Server.server>` to a instance of
        ``gevent.server.StreamServer``, and call its ``serve_forever`` method.

        All extra keyword arguments are passed to the constructor of
        ``StreamServer``.
        """
        self.server = StreamServer((host, port), handle=self.handle)
        self.server.serve_forever()
