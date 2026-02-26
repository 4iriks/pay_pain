import aiosqlite
from datetime import datetime
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                joined_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                plan_key    TEXT NOT NULL,
                months      INTEGER NOT NULL,
                amount      INTEGER NOT NULL,
                payment_id  TEXT,
                status      TEXT DEFAULT 'pending',   -- pending | active | expired | cancelled
                started_at  TEXT,
                expires_at  TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def get_setting(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as c:
            row = await c.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


async def upsert_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (user_id, username, full_name))
        await db.commit()


async def create_subscription(user_id: int, plan_key: str, months: int, amount: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO subscriptions (user_id, plan_key, months, amount)
            VALUES (?, ?, ?, ?)
        """, (user_id, plan_key, months, amount))
        await db.commit()
        return cursor.lastrowid


async def activate_subscription(sub_id: int, payment_id: str, expires_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE subscriptions
            SET status = 'active',
                payment_id = ?,
                started_at = datetime('now'),
                expires_at = ?
            WHERE id = ?
        """, (payment_id, expires_at, sub_id))
        await db.commit()


async def get_active_subscription(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY expires_at DESC
            LIMIT 1
        """, (user_id,)) as cursor:
            return await cursor.fetchone()


async def get_expired_subscriptions():
    """Вернуть все подписки, у которых expires_at < now и статус active."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
              AND expires_at < datetime('now')
        """) as cursor:
            return await cursor.fetchall()


async def expire_subscription(sub_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET status = 'expired' WHERE id = ?",
            (sub_id,)
        )
        await db.commit()


async def get_subscription_by_payment(payment_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions WHERE payment_id = ?
        """, (payment_id,)) as cursor:
            return await cursor.fetchone()


async def get_pending_subscription(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def extend_subscription(user_id: int, days: int):
    """Продлить активную подписку на N дней. Если нет активной — создать новую."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY expires_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            sub = await cursor.fetchone()

        if sub:
            await db.execute("""
                UPDATE subscriptions
                SET expires_at = datetime(expires_at, ? || ' days')
                WHERE id = ?
            """, (str(days), sub["id"]))
        else:
            expires_at = datetime.now()
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("""
                INSERT INTO subscriptions (user_id, plan_key, months, amount, status, started_at, expires_at, payment_id)
                VALUES (?, 'manual', ?, 0, 'active', datetime('now'), ?, 'manual')
            """, (user_id, days // 30 or 1, expires_at))
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()
