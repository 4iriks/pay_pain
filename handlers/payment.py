from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import PLANS
from database import (
    create_subscription, activate_subscription,
    get_pending_subscription
)
from services.yookassa import create_payment, check_payment
from keyboards.main import kb_payment, kb_after_payment, kb_back_main

router = Router()

PLAN_DESCRIPTIONS = {
    "1m": (
        "🥉 <b>Тариф: Старт — 1 месяц</b>\n\n"
        "💰 Стоимость: <b>399 ₽</b>\n"
        "📅 Срок: <b>30 дней</b>\n"
        "✅ Полный доступ к каналу\n\n"
        "Нажмите «Оплатить», чтобы продолжить 👇"
    ),
    "3m": (
        "🥈 <b>Тариф: Популярный — 3 месяца</b>\n\n"
        "💰 Стоимость: <b>699 ₽</b>  <s>1 197 ₽</s>\n"
        "📅 Срок: <b>90 дней</b>\n"
        "✅ Полный доступ к каналу\n"
        "🎁 Экономия: <b>41%</b>\n\n"
        "Нажмите «Оплатить», чтобы продолжить 👇"
    ),
    "12m": (
        "🥇 <b>Тариф: Выгодный — 12 месяцев</b>\n\n"
        "💰 Стоимость: <b>2 199 ₽</b>  <s>4 788 ₽</s>\n"
        "📅 Срок: <b>365 дней</b>\n"
        "✅ Полный доступ к каналу\n"
        "🎁 Экономия: <b>54%</b>\n\n"
        "Нажмите «Оплатить», чтобы продолжить 👇"
    ),
}


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan_selected(call: CallbackQuery):
    plan_key = call.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await call.answer("❌ Неверный тариф", show_alert=True)
        return

    # Создать запись подписки в БД (статус pending)
    sub_id = await create_subscription(
        user_id=call.from_user.id,
        plan_key=plan_key,
        months=plan["months"],
        amount=plan["price"]
    )

    # Создать платёж (заглушка / реальный)
    result = await create_payment(call.from_user.id, plan_key)

    # Сохранить payment_id в pending-подписке
    from database import activate_subscription as _act
    # Обновляем только payment_id, оставляем статус pending
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET payment_id = ? WHERE id = ?",
            (result.payment_id, sub_id)
        )
        await db.commit()

    desc = PLAN_DESCRIPTIONS.get(plan_key, "")
    if call.message.photo:
        await call.message.edit_caption(caption=desc, parse_mode="HTML", reply_markup=kb_payment(sub_id=sub_id, payment_url=result.confirmation_url))
    else:
        await call.message.edit_text(desc, parse_mode="HTML", reply_markup=kb_payment(sub_id=sub_id, payment_url=result.confirmation_url))
    await call.answer()


@router.callback_query(F.data.startswith("check_payment:"))
async def cb_check_payment(call: CallbackQuery):
    sub_id = int(call.data.split(":")[1])
    await call.answer("⏳ Проверяем платёж...", show_alert=False)

    # Получить pending-подписку
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, call.from_user.id)
        ) as cursor:
            sub = await cursor.fetchone()

    if not sub:
        await call.answer("❌ Подписка не найдена", show_alert=True)
        return

    if sub["status"] == "active":
        await call.answer("✅ Подписка уже активна!", show_alert=True)
        return

    payment_id = sub["payment_id"]
    status = await check_payment(payment_id)

    if status == "succeeded":
        await call.answer("✅ Оплата найдена!", show_alert=True)
        months = sub["months"]
        expires_at = (datetime.now() + timedelta(days=30 * months)).strftime("%Y-%m-%d %H:%M:%S")
        await activate_subscription(sub_id, payment_id, expires_at)

        plan_names = {"1m": "1 месяц", "3m": "3 месяца", "12m": "12 месяцев"}
        success_text = (
            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
            f"✅ Подписка активирована\n"
            f"📦 Тариф: <b>{plan_names.get(sub['plan_key'], sub['plan_key'])}</b>\n"
            f"⏳ Действует до: <b>{expires_at[:10]}</b>\n\n"
            f"Нажмите кнопку ниже, чтобы войти в канал 👇"
        )
        if call.message.photo:
            await call.message.edit_caption(caption=success_text, parse_mode="HTML", reply_markup=kb_after_payment())
        else:
            await call.message.edit_text(success_text, parse_mode="HTML", reply_markup=kb_after_payment())
    elif status == "cancelled":
        cancel_text = "❌ <b>Платёж отменён</b>\n\nПопробуйте снова или выберите другой способ оплаты."
        if call.message.photo:
            await call.message.edit_caption(caption=cancel_text, parse_mode="HTML", reply_markup=kb_back_main())
        else:
            await call.message.edit_text(cancel_text, parse_mode="HTML", reply_markup=kb_back_main())
    else:
        await call.answer("❌ Оплата не найдена", show_alert=True)
