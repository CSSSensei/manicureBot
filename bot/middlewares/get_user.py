import logging
from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware
from aiogram.exceptions import AiogramError
from aiogram.fsm.context import FSMContext
from aiogram.types import Update, User, Message

from DB.tables.users import UsersTable
from DB.models import UserModel as UserModel
from bot.states import UserStates
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)


class GetUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
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
                if not user_row.username and not user_row.contact:
                    if not isinstance(event.event, Message):
                        return await handler(event, data)

                    message: Message = event.event
                    state: FSMContext = data.get("state")
                    current_state = await state.get_state() if state else None

                    is_allowed_command = message.text and message.text.startswith(('/start', '/add_contact'))
                    is_contact_input_state = current_state == UserStates.WAITING_FOR_CONTACT

                    if is_allowed_command or is_contact_input_state:
                        return await handler(event, data)
                    await message.answer(PHRASES_RU.error.no_contact)
                    return
        except Exception as e:
            logger.error(f'Failed to process user {user.id}: {str(e)}', exc_info=True)
            raise AiogramError(f'User processing failed: {str(e)}') from e

        return await handler(event, data)
