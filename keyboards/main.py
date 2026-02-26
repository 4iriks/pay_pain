from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="1 месяц — 399 ₽",      callback_data="plan:1m"))
    builder.row(InlineKeyboardButton(text="3 месяца — 699 ₽",      callback_data="plan:3m"))
    builder.row(InlineKeyboardButton(text="12 месяцев — 2 199 ₽",  callback_data="plan:12m"))
    builder.row(InlineKeyboardButton(text="Моя подписка",           callback_data="my_sub"))
    return builder.as_markup()


def kb_payment(sub_id: int, payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплатить сейчас",        url=payment_url))
    builder.row(InlineKeyboardButton(text="Я оплатил — проверить",  callback_data=f"check_payment:{sub_id}"))
    builder.row(InlineKeyboardButton(text="Отмена",                  callback_data="back_main"))
    return builder.as_markup()


def kb_after_payment() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Войти в канал",   callback_data="join_channel"))
    builder.row(InlineKeyboardButton(text="Моя подписка",    callback_data="my_sub"))
    return builder.as_markup()


def kb_subscription_info(has_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_active:
        builder.row(InlineKeyboardButton(text="Войти в канал",      callback_data="join_channel"))
        builder.row(InlineKeyboardButton(text="Продлить подписку",  callback_data="back_main"))
    else:
        builder.row(InlineKeyboardButton(text="Оформить подписку",  callback_data="back_main"))
    builder.row(InlineKeyboardButton(text="Главное меню",           callback_data="back_main"))
    return builder.as_markup()


def kb_back_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="back_main"))
    return builder.as_markup()


def kb_admin_panel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Статистика",     callback_data="admin_stats"),
        InlineKeyboardButton(text="Пользователи",   callback_data="admin_users"),
    )
    builder.row(
        InlineKeyboardButton(text="Управление юзером", callback_data="admin_manage"),
    )
    builder.row(
        InlineKeyboardButton(text="Рассылка",  callback_data="admin_broadcast"),
        InlineKeyboardButton(text="Выход",     callback_data="back_main"),
    )
    return builder.as_markup()


def kb_admin_user_actions(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Продлить подписку",          callback_data=f"admin_extend:{user_id}"))
    builder.row(InlineKeyboardButton(text="Бан (выкинуть из канала)",   callback_data=f"admin_ban:{user_id}"))
    builder.row(InlineKeyboardButton(text="Назад",                       callback_data="admin_panel"))
    return builder.as_markup()


def kb_admin_back() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="К панели", callback_data="admin_panel"))
    return builder.as_markup()
