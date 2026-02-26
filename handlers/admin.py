import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, DB_PATH, PRIVATE_CHANNEL_ID
from database import get_all_users, get_user, get_active_subscription, extend_subscription, expire_subscription
from keyboards.main import kb_admin_panel, kb_admin_user_actions, kb_admin_back, kb_back_main

router = Router()


class AdminFSM(StatesGroup):
    waiting_user_id  = State()
    waiting_days     = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── /admin ──────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("🚫 Нет доступа")
        return
    await msg.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=kb_admin_panel()
    )


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text(
        "🛠 <b>Панель администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=kb_admin_panel()
    )
    await call.answer()


# ─── Статистика ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'") as c:
            active_subs = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='expired'") as c:
            expired_subs = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE status='pending'") as c:
            pending_subs = (await c.fetchone())[0]

        async with db.execute("SELECT SUM(amount) FROM subscriptions WHERE status IN ('active','expired')") as c:
            total_revenue = (await c.fetchone())[0] or 0

        async with db.execute("SELECT SUM(amount) FROM subscriptions WHERE status='active'") as c:
            active_revenue = (await c.fetchone())[0] or 0

        async with db.execute("""
            SELECT COUNT(*) FROM subscriptions
            WHERE status='active' AND expires_at <= datetime('now', '+3 days')
        """) as c:
            expiring_soon = (await c.fetchone())[0]

        async with db.execute("""
            SELECT plan_key, COUNT(*) as cnt FROM subscriptions
            WHERE status IN ('active','expired')
            GROUP BY plan_key ORDER BY cnt DESC
        """) as c:
            plan_stats = await c.fetchall()

        async with db.execute("""
            SELECT COUNT(*) FROM users
            WHERE joined_at >= datetime('now', '-7 days')
        """) as c:
            new_week = (await c.fetchone())[0]

    plan_names = {"1m": "1 мес", "3m": "3 мес", "12m": "12 мес", "manual": "Ручная"}
    plans_text = "  ".join(f"{plan_names.get(p, p)}: <b>{c}</b>" for p, c in plan_stats) or "—"

    text = (
        "📊 <b>Статистика</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🆕 Новых за 7 дней: <b>{new_week}</b>\n\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n"
        f"⚠️ Истекают через 3 дня: <b>{expiring_soon}</b>\n"
        f"❌ Истёкших: <b>{expired_subs}</b>\n"
        f"⏳ Ожидают оплаты: <b>{pending_subs}</b>\n\n"
        f"💰 Общая выручка: <b>{total_revenue} ₽</b>\n"
        f"💳 Активные подписки: <b>{active_revenue} ₽</b>\n\n"
        f"📦 По тарифам: {plans_text}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_admin_back())
    await call.answer()


# ─── Список пользователей ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.user_id, u.username, u.full_name,
                   s.status, s.expires_at, s.plan_key
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.user_id AND s.status = 'active'
            ORDER BY u.joined_at DESC
            LIMIT 30
        """) as cursor:
            rows = await cursor.fetchall()

        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total = (await c.fetchone())[0]

    text = f"👥 <b>Пользователи</b> (последние 30 из {total}):\n\n"
    plan_names = {"1m": "1м", "3m": "3м", "12m": "12м", "manual": "👑"}

    for r in rows:
        name = r["full_name"] or "—"
        uname = f"@{r['username']}" if r["username"] else ""
        sub_icon = "✅" if r["status"] == "active" else "❌"
        exp = f" до {r['expires_at'][:10]}" if r["expires_at"] else ""
        plan = f" [{plan_names.get(r['plan_key'], '')}]" if r["plan_key"] else ""
        text += f"{sub_icon} <code>{r['user_id']}</code> {name} {uname}{plan}{exp}\n"

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_admin_back())
    await call.answer()


# ─── Управление пользователем ─────────────────────────────────────────────────

@router.callback_query(F.data == "admin_manage")
async def cb_admin_manage(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return

    await state.set_state(AdminFSM.waiting_user_id)
    await call.message.edit_text(
        "🔧 <b>Управление пользователем</b>\n\n"
        "Введите <b>user_id</b> пользователя\n"
        "<i>Его можно найти в списке пользователей</i>",
        parse_mode="HTML",
        reply_markup=kb_admin_back()
    )
    await call.answer()


@router.message(AdminFSM.waiting_user_id)
async def fsm_got_user_id(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    raw = msg.text.strip().lstrip("@")
    if not raw.isdigit():
        await msg.answer("❗ Введите числовой user_id")
        return

    target_id = int(raw)
    user = await get_user(target_id)
    sub  = await get_active_subscription(target_id)

    if not user:
        await msg.answer("❌ Пользователь не найден в базе", reply_markup=kb_admin_back())
        await state.clear()
        return

    name   = user["full_name"] or "—"
    uname  = f"@{user['username']}" if user["username"] else "—"

    if sub:
        sub_text = (
            f"✅ Активна до <b>{sub['expires_at'][:10]}</b>\n"
            f"📦 Тариф: <b>{sub['plan_key']}</b>"
        )
    else:
        sub_text = "❌ Нет активной подписки"

    await state.update_data(target_id=target_id)
    await state.set_state(None)

    await msg.answer(
        f"👤 <b>Пользователь</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"ID: <code>{target_id}</code>\n"
        f"Имя: {name}\n"
        f"Username: {uname}\n\n"
        f"📋 Подписка: {sub_text}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=kb_admin_user_actions(target_id)
    )


# ─── Продлить ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_extend:"))
async def cb_admin_extend(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])
    await state.update_data(target_id=target_id)
    await state.set_state(AdminFSM.waiting_days)

    await call.message.edit_text(
        f"📅 <b>Продление подписки</b>\n\n"
        f"Пользователь: <code>{target_id}</code>\n\n"
        f"На сколько <b>дней</b> продлить?\n"
        f"<i>Примеры: 30, 90, 365</i>",
        parse_mode="HTML",
        reply_markup=kb_admin_back()
    )
    await call.answer()


@router.message(AdminFSM.waiting_days)
async def fsm_got_days(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    if not msg.text.strip().isdigit():
        await msg.answer("❗ Введите количество дней числом")
        return

    days = int(msg.text.strip())
    data = await state.get_data()
    target_id = data["target_id"]

    await extend_subscription(target_id, days)
    sub = await get_active_subscription(target_id)
    await state.clear()

    await msg.answer(
        f"✅ <b>Подписка продлена</b>\n\n"
        f"Пользователь: <code>{target_id}</code>\n"
        f"Добавлено дней: <b>{days}</b>\n"
        f"Действует до: <b>{sub['expires_at'][:10] if sub else '—'}</b>",
        parse_mode="HTML",
        reply_markup=kb_admin_back()
    )

    try:
        await msg.bot.send_message(
            target_id,
            f"🎁 <b>Ваша подписка продлена!</b>\n\n"
            f"Добавлено дней: <b>{days}</b>\n"
            f"Действует до: <b>{sub['expires_at'][:10] if sub else '—'}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── Бан ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_ban:"))
async def cb_admin_ban(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return

    target_id = int(call.data.split(":")[1])

    try:
        await call.bot.ban_chat_member(PRIVATE_CHANNEL_ID, target_id)
        await call.bot.unban_chat_member(PRIVATE_CHANNEL_ID, target_id)
    except Exception as e:
        await call.answer(f"⚠️ Ошибка кика: {e}", show_alert=True)

    # Деактивируем подписку в БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET status='expired' WHERE user_id=? AND status='active'",
            (target_id,)
        )
        await db.commit()

    await state.clear()
    await call.message.edit_text(
        f"🚫 <b>Пользователь заблокирован</b>\n\n"
        f"ID: <code>{target_id}</code>\n"
        f"Выкинут из канала, подписка деактивирована.",
        parse_mode="HTML",
        reply_markup=kb_admin_back()
    )

    try:
        await call.bot.send_message(
            target_id,
            "🚫 <b>Ваш доступ к каналу был отозван администратором.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await call.answer()


# ─── Рассылка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return
    await call.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Используй команду:\n<code>/broadcast Текст сообщения</code>",
        parse_mode="HTML",
        reply_markup=kb_admin_back()
    )
    await call.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    text = msg.text.removeprefix("/broadcast").strip()
    if not text:
        await msg.answer("❗ Укажите текст: /broadcast Привет!")
        return

    users = await get_all_users()
    ok, fail = 0, 0
    for u in users:
        try:
            await msg.bot.send_message(u["user_id"], text)
            ok += 1
        except Exception:
            fail += 1

    await msg.answer(f"📢 Рассылка завершена\n✅ Доставлено: {ok}\n❌ Ошибок: {fail}")
