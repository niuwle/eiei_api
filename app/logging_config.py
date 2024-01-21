import logging
from logging.config import dictConfig

def setup_logging():
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
            'sqlalchemy_engine': {
                'level': 'WARN',  # Set to WARN to reduce SQL logs
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': True
            },
            'sqlalchemy.engine': {
                'handlers': ['sqlalchemy_engine'],
                'level': 'WARN',  # Adjust this level as needed
                'propagate': False
            },
        }
    }

    dictConfig(logging_config)
