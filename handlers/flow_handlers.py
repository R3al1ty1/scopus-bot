from aiogram.types import Message, CallbackQuery
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state, State, StatesGroup
from aiogram_dialog import DialogManager, StartMode
from database.requests import new_user, enough_requests

from dialogs import dialogs
from handlers.service_handlers import process_payments_command


router = Router()

class FSMSearching(StatesGroup):   
    searching = State()

# Хендлер для команды /search
@router.message(Command(commands='search'), StateFilter(default_state))
async def process_search_command(message: Message, state: FSMContext, dialog_manager: DialogManager):
    chat_id = str(message.chat.id)
    username = str(message.chat.username)
    new_user(chat_id, username)
    if enough_requests(chat_id=chat_id):
        await dialog_manager.start(dialogs.FSMGeneral.choose_search, mode=StartMode.RESET_STACK)
    else:
        await message.answer("К сожалению, на вашем балансе закончились запросы.\nПриобретите их сейчас👇🏼")
        await process_payments_command(message)
        return

# Хендлер для нажатия кнопки search
@router.callback_query(F.data == "search_button_pressed", StateFilter(default_state))
async def process_search_button(callback: CallbackQuery, state: FSMContext, dialog_manager: DialogManager):
    chat_id = str(callback.message.chat.id)
    username = str(callback.message.chat.username)
    new_user(chat_id, username)
    if enough_requests(chat_id=chat_id):
        await dialog_manager.start(dialogs.FSMGeneral.choose_search, mode=StartMode.RESET_STACK)
    else:
        await callback.message.answer("К сожалению, на вашем балансе закончились запросы.\nПриобретите их сейчас👇🏼")
        await process_payments_command(callback.message)
        return



# @router.callback_query(lambda callback: callback.data.startswith("paginate"))
# async def handle_pagination(callback: CallbackQuery, manager: DialogManager):
#     """
#     Обработка кнопок пагинации.
#     """
#     # Получаем номер страницы из callback_data
#     page = int(callback.data.split(":")[1])

#     # Получаем результаты из dialog_data
#     items = manager.dialog_data.get('auths_found', [])

#     if not items:
#         await callback.message.answer("Результаты поиска недоступны. Попробуйте выполнить поиск заново.")
#         return

#     # Создаём клавиатуру для новой страницы
#     keyboard = dialogs.create_pagination_keyboard(items, page)
#     await callback.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(lambda callback: callback.data.startswith("select_item"))
async def handle_item_selection(callback: CallbackQuery, manager: DialogManager):
    """
    Обработка выбора элемента.
    """
    _, page, index = callback.data.split(":")
    page, index = int(page), int(index)

    # Получаем результаты из dialog_data
    items = manager.dialog_data.get('auths_found', [])
    if not items:
        await callback.message.answer("Результаты поиска недоступны. Попробуйте выполнить поиск заново.")
        return

    # Находим выбранный элемент
    item_index = page * 5 + index
    if item_index >= len(items):
        await callback.message.answer("Выбранный элемент недоступен.")
        return

    selected_item = items[item_index]

    # Отправляем информацию о выбранном элементе
    await callback.message.answer(
        text=f"Вы выбрали автора:\n"
             f"{selected_item['Author']}\n"
             f"Документы: {selected_item['Documents']}\n"
             f"Аффилиация: {selected_item['Affiliation']}"
    )
