"""
This is a custom logging module.

This module writes logs as a file and also to a URL.
Following env variables are used to control this module.
Note: Python's logs are by default thread safe.

env variable configs:
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL.
        Default is set to INFO
    - EXTERNAL_URL: A logging endpoint. This module will send a POST request to an external logging end point
        Default is set to no URL (None)
    - LOG_BACKUP_COUNT: An integer indicating the backup log file count. The max log file size_delta is 1MB.
        Default is set to 3

Usage:
    - Import logging module.
    - When logging,  use logging.info(<log string>), logging.error(), logging.debug(), logging.critical(), logging.warn(),
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import requests
import validators


def __setup_logger(log_level='INFO', external_url=None):
    # Create logs folder if not exists
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Configure the root logging
    # logging.basicConfig(level=log_level)
    # logging.basicConfig(level=logging.CRITICAL)

    # Create logging for all log levels
    logger = logging.getLogger(log_level)
    logger.setLevel(log_level)

    # Create file handler for logs
    log_file = "logs/app.log"

    log_backup_count = int(os.getenv('LOG_BACKUP_COUNT', '3'))
    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=log_backup_count)
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')  # Include the timestamp
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Create handler for sending logs to external URL
    class ExternalLogHandler(logging.Handler):
        def emit(self, record):
            log_data = self.format(record)
            if external_url != '':
                response = requests.post(external_url, data=log_data)
                if response.status_code != 200:
                    logger.error(f"Error sending log to external URL: {response.status_code}")

    if external_url:
        external_handler = ExternalLogHandler()
        external_handler.setLevel(log_level)
        external_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        external_handler.setFormatter(external_formatter)
        logger.addHandler(external_handler)


    return logger


__log_level = 'INFO'

if os.getenv('LOG_LEVEL') in ['INFO', 'CRITICAL', 'DEBUG',  'ERROR', 'WARNING']:
    __log_level = os.getenv('LOG_LEVEL')


__external_url = os.getenv('LOG_URL', '')

if not validators.url(__external_url):
    __external_url = ''

# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logger = __setup_logger(log_level=__log_level, external_url=__external_url)

