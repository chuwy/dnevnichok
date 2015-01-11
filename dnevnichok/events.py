import logging

logger = logging.getLogger(__name__)


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
        if event_name != 'show':
            logger.info("Trigger executed with " + str(event))
        if event_name in self._handlers:
            for handler in self._handlers[event_name]:
                handler(*event[1:])
        else:
            logger.debug("Unhandled event: " + str(event))



event_hub = EventHub()