import logging

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError  # For Python <3.8


def set_stream_logger(name, level=logging.DEBUG, format_string=None):
    """
    Adapted from boto3.set_stream_logger()
    """
    if format_string is None:
        format_string = \
            '%(addr)s - - [%(asctime)s] %(levelname)s - %(message)s'

    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(format_string, '%-d/%b/%Y %H:%M:%S')
    adapter = logging.LoggerAdapter(logger, dict(addr='::1'))
    logger.setLevel(level)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return adapter


def _version():
    """
    Helper to get package version.
    """
    try:
        return version("lambda-gateway")
    except PackageNotFoundError:  # pragma: no cover
        return None


__version__ = _version()

logger = set_stream_logger(__name__)
