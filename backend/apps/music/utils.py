import logging

logger = logging.getLogger(__name__)

class MockStorageConnector:
    def __init__(self, *args, **kwargs):
        logger.info("MockStorageConnector initialized with args: %s, kwargs: %s", args, kwargs)

    def __getattr__(self, name):
        def method(*args, **kwargs):
            logger.info(f"Mock method '{name}' called with args={args}, kwargs={kwargs}")
            return True 
        return method
