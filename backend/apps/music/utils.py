import logging

logger = logging.getLogger(__name__)

class MockStorageConnector:
    def __init__(self, *args, **kwargs):
        logger.info("MockStorageConnector initialized with args: %s, kwargs: %s", args, kwargs)

    def __getattr__(self, name):
        def method(*args, **kwargs):
            logger.info(f"Mock method '{name}' called with args={args}, kwargs={kwargs}")
            if len(args) > 1 and isinstance(args[1], str):
                return args[1]
            return "tracks/test/mock_file.mp3"
        return method
