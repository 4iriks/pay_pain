"""
Фоновый планировщик: каждые 10 минут проверяет истёкшие подписки
и кикает пользователей из закрытого канала.
"""
import asyncio
import logging
import aiosqlite
from aiogram import Bot
from database import get_expired_subscriptions, expire_subscription
from config import PRIVATE_CHANNEL_ID, DB_PATH

log = logging.getLogger(__name__)


async def kick_expired(bot: Bot):
    """Найти истёкшие подписки → кикнуть пользователей → обновить БД."""
    expired = await get_expired_subscriptions()
    if not expired:
        return

    for sub in expired:
        user_id = sub["user_id"]
        sub_id  = sub["id"]
        try:
            await bot.ban_chat_member(PRIVATE_CHANNEL_ID, user_id)
            await bot.unban_chat_member(PRIVATE_CHANNEL_ID, user_id)  # сразу снять бан, чтобы мог вернуться
            await expire_subscription(sub_id)
            log.info(f"Кикнул пользователя {user_id} (sub #{sub_id}) — подписка истекла")

            await bot.send_message(
                user_id,
                "⏰ <b>Ваша подписка закончилась!</b>\n\n"
                "Доступ к закрытому каналу приостановлен.\n"
                "Нажмите /start чтобы продлить подписку 👇",
                parse_mode="HTML"
            )
        except Exception as e:
            log.warning(f"Ошибка при кике пользователя {user_id}: {e}")
            await expire_subscription(sub_id)


async def cancel_stale_pending():
    """Отменить pending-платежи старше 1 часа."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id FROM subscriptions
            WHERE status = 'pending'
              AND created_at < datetime('now', '-1 hour')
        """) as cursor:
            rows = await cursor.fetchall()

        if rows:
            ids = [r[0] for r in rows]
            await db.execute(
                f"UPDATE subscriptions SET status = 'cancelled' WHERE id IN ({','.join('?' * len(ids))})",
                ids
            )
            await db.commit()
            log.info(f"Отменено старых pending-платежей: {len(ids)}")


async def run_scheduler(bot: Bot, interval: int = 600):
    """Запускать проверку каждые `interval` секунд (по умолчанию — 10 мин)."""
    log.info("Планировщик подписок запущен")
    while True:
        try:
            await kick_expired(bot)
            await cancel_stale_pending()
        except Exception as e:
            log.error(f"Ошибка в планировщике: {e}")
        await asyncio.sleep(interval)
