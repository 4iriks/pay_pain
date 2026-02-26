import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PRIVATE_CHANNEL_ID
from database import init_db, get_setting, set_setting
from handlers import start, payment, admin, join_request
from services.scheduler import run_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


async def main():
    log.info("Инициализация базы данных...")
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(join_request.router)
    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)

    # Создать постоянную join-request ссылку если ещё нет
    existing = await get_setting("invite_link")
    if not existing:
        try:
            link = await bot.create_chat_invite_link(
                PRIVATE_CHANNEL_ID,
                name="Подписка",
                creates_join_request=True
            )
            await set_setting("invite_link", link.invite_link)
            log.info(f"Создана join-request ссылка: {link.invite_link}")
        except Exception as e:
            log.error(f"Не удалось создать ссылку: {e}")

    # Запускаем планировщик в фоне
    asyncio.create_task(run_scheduler(bot))

    log.info("Бот запущен!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
