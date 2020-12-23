#!/usr/bin/python
import time
import signal
import sys
import logging

logger = logging.getLogger("helloworld")
logging.basicConfig(level=logging.DEBUG)


def handler(signum, frame):
    logger.debug(f'Signal handler called with signal {signum}')
    logger.debug("Bye world")
    sys.exit(0)

signal.signal(signal.SIGTERM, handler)
logger.debug("Hello world announce")

while True:
    time.sleep(60)
    logger.debug("Hello world loop")
