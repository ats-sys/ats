from pydantic import ValidationError
import traceback
import os
from ats.utils.logging.logger import logger


def exception_to_response(e: Exception) -> dict:
    """
    Convert an exception into a response
    Args:
        e: Exception

    Returns:
        Dict with response information
    """
    message = 'Internal Server Error'
    response = {'message': message}

    if hasattr(e, "show_in_response") and e.show_in_response:
        response['error'] = type(e).__name__
        response['detail'] = str(e)

    elif isinstance(e, ValidationError):
        response['error'] = type(e).__name__
        response['detail'] = str(e.errors()[0]['msg'])

    elif os.getenv('LOG_LEVEL') == 'DEBUG' and 1 == 2:
        response['error'] = type(e).__name__
        response['detail'] = str(e.errors()[0]['msg'])

    else:
        response['error'] = 'Generic error'
        response['detail'] = 'Set LOG_LEVEL to DEBUG to view the error message'

    logger.error(str(e))

    if os.getenv('LOG_LEVEL') == 'DEBUG':
        traceback.print_exc()

    return response


def raise_and_show_in_response(e: Exception):
    e.show_in_response = True
    raise e