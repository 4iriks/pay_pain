from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import upsert_user, get_active_subscription, get_pending_subscription, get_setting
from keyboards.main import kb_main_menu, kb_subscription_info, kb_back_main

WELCOME_PHOTO = "photo/photo_2026-02-26_23-05-28.jpg"

router = Router()

WELCOME_TEXT = (
    "👋 <b>Привет, {name}!</b>\n\n"
    "Добро пожаловать в приватный канал только для премиум подписчиков.\n\n"
    "Вас ждет:\n\n"
    "Эксклюзивный 18+ контент, общение, и исполнение сокровенных желаний.\n\n"
    "Выбери срок подписки и получи доступ прямо сейчас:"
)


@router.message(CommandStart())
async def cmd_start(msg: Message):
    user = msg.from_user
    await upsert_user(user.id, user.username or "", user.full_name)

    # Если есть незавершённый платёж — напомнить
    pending = await get_pending_subscription(user.id)
    if pending:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅  Я оплатил — проверить",
            callback_data=f"check_payment:{pending['id']}",
            style="success"
        ))
        builder.row(InlineKeyboardButton(
            text="❌  Отменить, выбрать другой тариф",
            callback_data="back_main",
            style="danger"
        ))
        plan_names = {"1m": "1 месяц", "3m": "3 месяца", "12m": "12 месяцев"}
        await msg.answer(
            f"⏳ <b>У вас есть незавершённая оплата</b>\n\n"
            f"📦 Тариф: <b>{plan_names.get(pending['plan_key'], pending['plan_key'])}</b>\n"
            f"💰 Сумма: <b>{pending['amount']} ₽</b>\n\n"
            f"Если вы уже оплатили — нажмите кнопку ниже и мы проверим платёж.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return

    await msg.answer_photo(
        photo=FSInputFile(WELCOME_PHOTO),
        caption=WELCOME_TEXT.format(name=user.first_name),
        parse_mode="HTML",
        reply_markup=kb_main_menu()
    )


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery):
    # Если предыдущее сообщение с фото — редактируем caption, иначе шлём новое
    if call.message.photo:
        await call.message.edit_caption(
            caption=WELCOME_TEXT.format(name=call.from_user.first_name),
            parse_mode="HTML",
            reply_markup=kb_main_menu()
        )
    else:
        await call.message.delete()
        await call.message.answer_photo(
            photo=FSInputFile(WELCOME_PHOTO),
            caption=WELCOME_TEXT.format(name=call.from_user.first_name),
            parse_mode="HTML",
            reply_markup=kb_main_menu()
        )
    await call.answer()


@router.callback_query(F.data == "my_sub")
async def cb_my_sub(call: CallbackQuery):
    sub = await get_active_subscription(call.from_user.id)

    if sub:
        expires = sub["expires_at"]
        plan    = sub["plan_key"]
        plan_names = {"1m": "1 месяц", "3m": "3 месяца", "12m": "12 месяцев"}
        text = (
            "📋 <b>Ваша подписка</b>\n\n"
            f"✅ Статус: <b>Активна</b>\n"
            f"📦 Тариф: <b>{plan_names.get(plan, plan)}</b>\n"
            f"⏳ Действует до: <b>{expires[:10]}</b>\n"
        )
    else:
        text = (
            "📋 <b>Ваша подписка</b>\n\n"
            "❌ Статус: <b>Нет активной подписки</b>\n\n"
            "Оформите подписку, чтобы получить доступ к закрытому каналу 👇"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=kb_subscription_info(has_active=bool(sub))
    )
    await call.answer()




@router.callback_query(F.data == "join_channel")
async def cb_join_channel(call: CallbackQuery):
    sub = await get_active_subscription(call.from_user.id)
    if not sub:
        await call.answer("❌ У вас нет активной подписки!", show_alert=True)
        return

    invite_link = await get_setting("invite_link")
    if not invite_link:
        await call.answer("⚠️ Ошибка, напишите администратору", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀  Подать заявку в канал", url=invite_link, style="success"))
    builder.row(InlineKeyboardButton(text="🏠  Главное меню", callback_data="back_main"))

    await call.message.edit_text(
        "🎉 <b>Подписка активна!</b>\n\n"
        "Нажмите кнопку ниже и подайте заявку на вступление.\n"
        "Бот одобрит её автоматически в течение нескольких секунд.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await call.answer()
