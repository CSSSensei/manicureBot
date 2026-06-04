import inspect

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from bot.bot_utils.filters import AdminFilter, MasterFilter
from bot.bot_utils.models import CommandUnit


class BaseRouter(Router):
    available_commands: list[CommandUnit] = []
    is_admin: bool = False  # По умолчанию не админский роутер
    is_master: bool = False
    is_user: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message.filter(F.chat.type == ChatType.PRIVATE)
        if self.is_admin:
            self.message.filter(AdminFilter())
        elif self.is_master:
            self.message.filter(MasterFilter())

    def command(self, command: str | tuple[str, ...], description: str = '', *placeholders):
        def decorator(handler):
            commands = (command,) if isinstance(command, str) else command
            self.available_commands.append(
                CommandUnit(
                    commands[0],
                    commands[1:],
                    description,
                    self.is_admin,
                    self.is_master,
                    self.is_user,
                    placeholders if placeholders else None,
                )
            )

            @self.message(Command(*commands, ignore_case=True))
            async def wrapper(message: Message, **kwargs):
                if 'state' in inspect.signature(handler).parameters:
                    await handler(message, state=kwargs.get('state'))
                else:
                    await handler(message)

            return handler

        return decorator


class AdminRouter(BaseRouter):
    is_admin = True


class MasterRouter(BaseRouter):
    is_master = True


class UserRouter(BaseRouter):
    is_user = True
