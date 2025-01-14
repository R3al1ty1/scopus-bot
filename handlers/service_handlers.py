from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import default_state
from aiogram_dialog import DialogManager

from utils.payments import buy_requests, check_payment_status, get_requests_amount
from utils.const import AMOUNTS_DCT
from database.requests import get_requests, add_requests, get_subscription_status, new_user


router = Router()

# Кнопки и клавиатуры
search_button = InlineKeyboardButton(text='ПОИСК', callback_data='search_button_pressed')
keyboard = InlineKeyboardMarkup(inline_keyboard=[[search_button]])

button_1 = InlineKeyboardButton(text='1', callback_data='button_1')
button_5 = InlineKeyboardButton(text='5', callback_data='button_5')
button_10 = InlineKeyboardButton(text='10', callback_data='button_10')
button_20 = InlineKeyboardButton(text='20', callback_data='button_20')
button_small = InlineKeyboardButton(text='SmallLab', callback_data='small')
button_medium = InlineKeyboardButton(text='MediumLab', callback_data='medium')
button_large = InlineKeyboardButton(text='LargeLab', callback_data='large')
button_sub = InlineKeyboardButton(text='Подписка на 30 дней', callback_data='subscription')

keyboard_payments = InlineKeyboardMarkup(inline_keyboard=[
    [button_1, button_5, button_10, button_20],
    [button_sub]
])


# Хендлеры
@router.message(Command(commands='help'), StateFilter(default_state))
async def process_help_command(message: Message):
    """Обработчик команды /help."""
    await message.answer(text="""
/search   - поиск
/payments - пополнение баланса
/support  - связь с поддержкой
/balance  - баланс

Краткий гайд по использованию бота:
https://telegra.ph/Kak-ispolzovat-ScopusRuBot-12-04
"""
    )


@router.message(Command(commands='start'), StateFilter(default_state))
async def process_start_command(message: Message):
    """Обработчик команды /start."""
    chat_id = str(message.chat.id)
    username = str(message.chat.username)
    new_user(chat_id, username)
    await message.answer(
        text="Привет! 👋 Этот бот поможет вам легко и быстро получить доступ к функционалу Скопус.\n\nВоспользуйтесь кнопкой ниже или введите /search.\n\n🎉 Поздравляем! Вы активировали 7 дней неограниченного пробного периода!",
        reply_markup=keyboard
    )


@router.message(Command(commands='payments'), StateFilter(default_state))
async def process_payments_command(message: Message):
    """Обработчик команды /payments."""
    await message.answer(
        text="""💰 Выберите, пожалуйста, количество запросов для покупки:

Подписка на 30 дней - 299 рублей
1 запрос -  29 руб
5 запросов -  149 руб
10 запросов -  269 руб
20 запросов -  449 руб

""",
        reply_markup=keyboard_payments
    )


@router.callback_query(F.data.in_(['button_1', 'button_5', 'button_10', 'button_20', 'small', 'medium', 'large', 'subscription']))
async def generate_payment(callback: CallbackQuery):
    """Формирование платежа и его проверки."""
    amount = AMOUNTS_DCT[callback.data]
    payment_url, payment_id = buy_requests(amount, callback.message.chat.id)
    url = InlineKeyboardButton(text="Оплата", url=payment_url)
    check = InlineKeyboardButton(text="Проверить оплату", callback_data=f'check_{payment_id}')
    keyboard_buy = InlineKeyboardMarkup(inline_keyboard=[[url, check]])

    await callback.message.answer(text="🔗 Ваша ссылка на оплату готова!\nПосле оплаты нажмите кнопку проверки платежа.",
                         reply_markup=keyboard_buy)


@router.callback_query(lambda x: "check" in x.data)
async def check_payment(callback: CallbackQuery):
    """Кнопка проверки платежа."""
    res = check_payment_status(callback.data.split('_')[-1])
    reqs = get_requests_amount(callback.data.split('_')[-1])
    if res:
        add_requests(callback.message.chat.id, reqs)
        if reqs == 0:
            await callback.message.answer(f"✅ Оплата успешно завершена, подписка активирована.")
        elif reqs == 1:
            await callback.message.answer(f"✅ Оплата успешно завершена, на баланс зачислен 1 запрос.")
        else:
            await callback.message.answer(f"✅ Оплата успешно завершена, на баланс зачислено {reqs} запросов.")
    else:
        await callback.message.answer("⌛️ Оплата еще не прошла.")


@router.message(Command(commands='support'), StateFilter(default_state))
async def process_support_command(message: Message):
    """Обработчик команды /support."""
    await message.answer(text="💬 Поддержка: @chadbugsy")


@router.message(Command(commands='balance'), StateFilter(default_state))
async def process_balance_command(message: Message):

    requests = get_requests(message.chat.id)
    sub_status, end_sub = get_subscription_status(message.chat.id)
    if sub_status == 'активна':
        if not requests:
            await message.answer(f"Ваша подписка {sub_status} до {end_sub}.\n💳 Чтобы пополнить баланс, используйте команду /payments.")
        else:
            await message.answer(f"Ваша подписка {sub_status} до {end_sub}.\n Количество запросов на Вашем счету: {requests}\n\n💳 Чтобы пополнить баланс, используйте команду /payments.")
    else:
        if not requests:
            await message.answer(f"Ваша подписка {sub_status} {end_sub}.\n💳 Чтобы приобрести новую, используйте команду /payments.")
        else:
            await message.answer(f"Количество запросов на вашем счету: {requests}.\n💳 Чтобы пополнить баланс, используйте команду /payments.")
