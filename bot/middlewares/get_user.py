import logging
from typing import Any, Awaitable, Callable, Optional, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import AiogramError
from aiogram.types import Update, User

from DB.tables.users import UsersTable
from DB.models import UserModel as UserModel

logger = logging.getLogger(__name__)


class GetUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:

        user: User = data.get('event_from_user')

        if user is None:
            return await handler(event, data)

        try:
            with UsersTable() as users_db:
                user_row: Optional[UserModel] = users_db.get_user(user.id)
                if (not user_row or user.username != user_row.username
                        or user.first_name != user_row.first_name or user.last_name != user_row.last_name):
                    new_user = UserModel(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                    user_row = users_db.add_user(new_user)
                data.update(user_row=user_row)
        except Exception as e:
            logger.error(f'Failed to process user {user.id}: {str(e)}', exc_info=True)
            raise AiogramError(f'User processing failed: {str(e)}') from e

        return await handler(event, data)
