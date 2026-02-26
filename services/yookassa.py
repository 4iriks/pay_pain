import uuid
from yookassa import Configuration, Payment as YKPayment
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, PLANS, BOT_TOKEN

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Ссылка куда вернётся пользователь после оплаты (в бота)
RETURN_URL = "https://t.me/fialoves_bot"


class PaymentResult:
    def __init__(self, payment_id: str, confirmation_url: str, status: str):
        self.payment_id = payment_id
        self.confirmation_url = confirmation_url
        self.status = status


async def create_payment(user_id: int, plan_key: str) -> PaymentResult:
    plan = PLANS[plan_key]
    idempotency_key = str(uuid.uuid4())

    payment = YKPayment.create({
        "amount": {
            "value": f"{plan['price']}.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": RETURN_URL
        },
        "capture": True,
        "description": f"Подписка {plan['label']}",
        "metadata": {
            "user_id": str(user_id),
            "plan_key": plan_key
        }
    }, idempotency_key)

    return PaymentResult(
        payment_id=payment.id,
        confirmation_url=payment.confirmation.confirmation_url,
        status=payment.status
    )


async def check_payment(payment_id: str) -> str:
    """Проверить статус платежа. Возвращает: pending | succeeded | cancelled."""
    payment = YKPayment.find_one(payment_id)
    return payment.status
