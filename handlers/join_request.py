from aiogram import Router, Bot
from aiogram.types import ChatJoinRequest
from database import get_active_subscription
from config import PRIVATE_CHANNEL_ID

router = Router()


@router.chat_join_request()
async def handle_join_request(request: ChatJoinRequest, bot: Bot):
    if request.chat.id != PRIVATE_CHANNEL_ID:
        return

    user_id = request.from_user.id
    sub = await get_active_subscription(user_id)

    if sub:
        await bot.approve_chat_join_request(PRIVATE_CHANNEL_ID, user_id)
    else:
        await bot.decline_chat_join_request(PRIVATE_CHANNEL_ID, user_id)
        try:
            await bot.send_message(
                user_id,
                "❌ <b>Доступ закрыт</b>\n\n"
                "У вас нет активной подписки.\n"
                "Нажмите /start чтобы оформить её.",
                parse_mode="HTML"
            )
        except Exception:
            pass
