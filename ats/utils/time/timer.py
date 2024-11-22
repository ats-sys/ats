import threading
import time
from typing import Callable
from ats.utils.logging.logger import logger


class Timer:
    """
    Time object runs a callable according to an interval
    """
    def __init__(self, on_timer: Callable, interval: int, no_threading=False):
        """
        Initiates the timer object
        Args:
            on_timer: callable such as a lambda function or a method
            interval: int, interval in seconds
        """
        self._callable = on_timer
        self._interval = interval
        self._is_running = False
        self._no_threading = no_threading

        if not self._no_threading:
            self._thread = threading.Thread(target=self._run)
            # self._thread.daemon = True

    def start(self):
        """Start the timer"""
        logger.info('Timer started.')
        self._is_running = True
        if not self._no_threading:
            self._thread.start()
        else:
            self._run()

    def delete(self):
        """Delete the timer"""
        logger.info('Timer stopping.')
        self._is_running = False

        if not self._no_threading:
            self._thread.join()

        logger.info('Timer stopped and deleted.')

        del self

    def is_running(self):
        """
        Check if the timer is running
        Returns:
            bool, True if the timer is running, False else
        """
        return self._is_running

    def _run(self):
        while self._is_running:
            self._callable()
            count = 0

            # If we use a longer sleep duration and use time.sleep( <long duration>), interrupting sleep becomes messy.
            # One trick is to use a default shorter time.sleep(<short duration>) and handle longer sleeps with a loop
            while count < self._interval and self._is_running:
                time.sleep(1)
                count += 1

