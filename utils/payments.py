import uuid
import os

from yookassa import Configuration, Payment
from dotenv import load_dotenv

from utils.const import REQUESTS_DCT, DESCRIPTIONS_DCT 


load_dotenv()


def buy_requests(amount, chat_id):
    """"Формирование платежа."""
    Configuration.configure(account_id=os.getenv('ACCOUNT-ID'), secret_key=os.getenv('SECRET-KEY'))
    id_key = str(uuid.uuid4())
    payment = Payment.create({
        "amount": {
            "value": amount,
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/ScopusRuBot"
        },
        "capture": True,
        "metadata": {
            'chat_id': chat_id
        },
        "description": DESCRIPTIONS_DCT[amount]
    }, id_key)

    return payment.confirmation.confirmation_url, payment.id


def check_payment_status(payment_id):
    """Проверка статуса платежа."""
    payment = Payment.find_one(payment_id=payment_id)
    if payment.status == "succeeded":
        return payment.metadata
    else:
        return False


def get_requests_amount(payment_id):
    """Формирование количества запросов для покупки."""
    payment = Payment.find_one(payment_id=payment_id)
    amount = int(payment.amount.value)

    return REQUESTS_DCT[amount]
