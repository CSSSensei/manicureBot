import logging
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram.types import Message, TelegramObject, InlineQuery

from DB.tables.queries import QueriesTable
from DB.models import UserModel as UserModel, QueryModel
from bot.bot_utils.routers import BaseRouter


logger = logging.getLogger(__name__)


class UserLoggerMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        #   <-| ----------------- -<phasalo>- ------------------ |->
        #                                                          |
        #     логгирование или своя логика                         | <=| PHASALO<|||
        #                                                          |
        #   <-| ----------------- -<phasalo>- ------------------ |->

        # phasalo ON
        if isinstance(event, Message):
            skip_commands = [
                f'/{cmd}'
                for command in BaseRouter.available_commands
                if command.is_admin
                for cmd in [command.name] + list(command.aliases)
            ]
            if event.text and any(event.text.startswith(cmd) for cmd in skip_commands):
                return await handler(event, data)
        user_row: Optional[UserModel] = data.get('user_row')
        if user_row is None:
            logger.warning(
                'Cannot add queries. The \'user_row\' '
                'key was not found in the middleware data.'
            )
            return await handler(event, data)

        # Логируем текстовые сообщения
        if isinstance(event, Message) and event.text:
            with QueriesTable() as queries_db:
                queries_db.add_query(QueryModel(user_row.user_id, event.text))

        # Логируем инлайн-запросы
        elif isinstance(event, InlineQuery) and event.query:
            with QueriesTable() as queries_db:
                queries_db.add_query(QueryModel(user_row.user_id, f'[INLINE] {event.query}'))
        # phasalo OFF

        return await handler(event, data)
