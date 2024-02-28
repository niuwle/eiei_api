from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


from .telegram_config import TelegramConfig
from .message import tbl_msg
from .awaiting_user_input import tbl_300_awaiting_user_input
from .payments import Payment
from .user_credits import UserCredit
from .user_info import tbl_150_user_info