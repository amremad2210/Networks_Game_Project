import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s - %(message)s")
logger = logging.getLogger()

def log_message(level, component, message):
    PAD = 15
    msg = f"{component.ljust(PAD)} | {message}"
    level = level.upper()

    if level == "INFO":
        logger.info(msg)
    elif level == "DEBUG":
        logger.debug(msg)
    elif level == "ERROR":
        logger.error(msg)
    elif level == "WARNING":
        logger.warning(msg)
    elif level == "CRITICAL":
        logger.critical(msg)
