import logging

logger = logging.getLogger(__name__)

# For some moment it seemed that for synchronous TUI app it would be enough to have such event system
# I was wrong, it's very cumbersome to handle all these event and need to refactor
# For now here are all app events:
# reload - get all items to manager and sequently fire `show items`
# show - show passed items in window
# print - print something to status bar


class EventHub:
    """ Primitive borg observable """

    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        self._handlers = {}

    def register(self, event: str, handler: callable):
        if event in self._handlers and handler not in self._handlers[event]:
            self._handlers[event].add(handler)
        elif event not in self._handlers:
            self._handlers[event] = {handler}

    def trigger(self, event: tuple):
        event_name = event[0]
        if event_name in self._handlers:
            for handler in self._handlers[event_name]:
                handler(*event[1:])
        else:
            logger.debug("Unhandled event: " + str(event))



event_hub = EventHub()
