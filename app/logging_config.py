import logging
from logging.config import dictConfig
from logging import StreamHandler

class CustomFormatter(logging.Formatter):
    """Custom formatter to add color for terminal output for different log levels."""
    FORMATS = {
        logging.DEBUG: "%(asctime)s - %(name)s - [DEBUG] - %(message)s",
        logging.INFO: "%(asctime)s - %(name)s - [INFO] - %(message)s",
        logging.WARNING: "%(asctime)s - %(name)s - [WARNING] - %(message)s",
        logging.ERROR: "\033[91m%(asctime)s - %(name)s - [ERROR] - %(message)s\033[0m",  # Red color for errors
        logging.CRITICAL: "\033[91m%(asctime)s - %(name)s - [CRITICAL] - %(message)s\033[0m",  # Red color for critical
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
def setup_logging():
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                # Added emojis for visual differentiation of log levels
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': {
            'default': {
                'level': 'DEBUG',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
            'sqlalchemy_engine': {
                'level': 'WARN',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'DEBUG',
                'propagate': True
            },
            'sqlalchemy.engine': {
                'handlers': ['sqlalchemy_engine'],
                'level': 'WARN',
                'propagate': False
            },
        }
    }

    # Customizing the format with icons for different log levels
    logging_config['formatters']['standard']['format'] = (
        '%(asctime)s - %(name)s - '
        + {
            'DEBUG': '🐛 DEBUG',
            'INFO': 'ℹ️ INFO',
            'WARNING': '⚠️ WARNING',
            'ERROR': '❗️ ERROR',
            'CRITICAL': '‼️ CRITICAL'
        }.get('%(levelname)s', '%(levelname)s') + ' - %(message)s'
    )

    dictConfig(logging_config)
