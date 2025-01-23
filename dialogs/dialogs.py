import uuid
import traceback
import requests
import asyncio
import shutil
import os
import zipfile
import aiohttp

from typing import Any
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InputMediaPhoto, InputFile
from aiogram import F
from io import BytesIO
from aiogram.types import FSInputFile, CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager, ShowMode
from aiogram_dialog.widgets.text import Format,Const
from aiogram_dialog.widgets.kbd import Checkbox, Button, Row, Next, ScrollingGroup
from aiogram_dialog.widgets.input import TextInput
from dotenv import load_dotenv

from database.requests import new_user, charge_request, add_requests_error
from utils.utils import download_scopus_file, downloads_done, search_for_author_cred, get_author_info
from utils.unzipper import unzip_pngs
from handlers.service_handlers import process_payments_command
from utils.const import PROJECT_DIR

load_dotenv()

addr = os.getenv('SERVER_ADDRESS')

class FSMGeneral(StatesGroup):
    choose_search = State()
    name_or_orcid = State()
    orcid = State()
    full_name = State()
    keywords = State()
    check_auths = State()
    check_auths_key = State()
    validate_auth = State()
    auth_info = State()


    choose_language = State()         # Состояние ожидания выбора языка
    choose_years = State()            # Состояние ожидания ввода годов
    choose_document_type = State()    # Состояние ожидания выбора типов документа
    choose_filter_type = State()
    filling_query = State()           # Состояние написания запроса
    validate_pubs = State()                # Валидация введенных данных
    check_pubs = State()              # Просмотр 50 статей
    choose_download_type = State()

async def dialog_get_data(dialog_manager: DialogManager, **kwargs):
    filter_type = ""

    if dialog_manager.find("title").is_checked():
        filter_type = "Title"
    elif dialog_manager.find("keywords").is_checked():
        filter_type = "Keywords"
    elif dialog_manager.find("authors").is_checked():
        filter_type = "Authors"
    elif dialog_manager.find("tak").is_checked():
        filter_type = "Title-abstract-keywords"

    return {
        "ru": dialog_manager.find("ru").is_checked(),
        "eng": dialog_manager.find("eng").is_checked(),
        "years": dialog_manager.find("years").get_value(),
        "art": dialog_manager.find("art").is_checked(),
        "rev": dialog_manager.find("rev").is_checked(),
        "conf": dialog_manager.find("conf").is_checked(),
        "filter_type": filter_type,
        "query": dialog_manager.find("query").get_value(),
        "pressed": dialog_manager.dialog_data['pressed'],
    }


async def get_current_status(folder_id, status_number, retries):
    for i in range(retries):
        try:
            await asyncio.sleep(10)
            status_number = str(status_number)
            url = f"https://scopus.baixo.keenetic.pro:8443/status/{folder_id}/{status_number}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as response:
                    data = await response.json()
                    if data.get('status') == "true":
                        return True
                    elif data.get('status') == "failed":
                        return False
        except:
            return False
    return False


async def dialog_authors(dialog_manager: DialogManager, **kwargs):
    
    if dialog_manager.find("full_name").is_checked():
        author_search_type = "Фамилия, имя"
        query = "name_search"
    elif dialog_manager.find("orcid").is_checked():
        author_search_type = "ORCID"
        query = "orcid_search"
    else:
        author_search_type = "Ключевые слова"
        query = "keywords_auth_search"


    return {
        "auth_search_type": author_search_type,
        "query": dialog_manager.find(query).get_value(),
        "pressed": dialog_manager.dialog_data['pressed'],
    }

async def pubs_found(dialog_manager: DialogManager, **kwargs):
    return {
        "pubs_found": dialog_manager.dialog_data['pubs_found'],
        "pressed_new": dialog_manager.dialog_data['pressed_new'],
    }


async def on_checkbox_click_pubs(event, widget, manager: DialogManager):
    selected_id = widget.widget_id

    checkboxes = [
        manager.dialog().find("title"),
        manager.dialog().find("keywords"),
        manager.dialog().find("authors"),
        manager.dialog().find("tak")
    ]

    for checkbox in checkboxes:
        if checkbox.widget_id != selected_id:
            await checkbox.set_checked(event=event, checked=False, manager=manager)
        else:
            await checkbox.set_checked(event=event, checked=True, manager=manager)

    selected_filter = {
        "title": "Title",
        "keywords": "Keywords",
        "authors": "Authors",
        "tak": "Title-abs-key",
    }.get(selected_id, "Title-abs-key")

    await manager.update(data={"selected_filter": selected_filter})


async def on_checkbox_search(event, widget, manager: DialogManager):
    selected_id = widget.widget_id

    checkboxes = [
        manager.dialog().find("author"),
        manager.dialog().find("article"),
    ]

    for checkbox in checkboxes:
        if checkbox.widget_id != selected_id:
            await checkbox.set_checked(event=event, checked=False, manager=manager)
        else:
            await checkbox.set_checked(event=event, checked=True, manager=manager)

    selected_search = {
        "article": "article",
        "author": "author",
    }.get(selected_id, "article")

    await manager.update(data={"search_type": selected_search})


async def choose_search_type(callback: CallbackQuery, button: Button, manager: DialogManager):
    search_type = manager.dialog_data.get("search_type", None)

    if search_type == "article":
        manager.dialog_data["search_type"] = ""
        # await manager.done()
        await manager.start(FSMGeneral.choose_language)  # Use start() to enter a different state group
        #await manager.switch_to(FSMGeneral.choose_language)
        
    elif search_type == "author":
        manager.dialog_data["search_type"] = ""
        # await manager.done()
        await manager.start(FSMGeneral.name_or_orcid)
        #await manager.switch_to(FSMGeneral.name_or_orcid)


async def author_search_type(event, widget, manager: DialogManager, *args, **kwargs):
    selected_id = widget.widget_id

    checkboxes = [
        manager.dialog().find("full_name"),
        manager.dialog().find("orcid"),
        manager.dialog().find("keywords_auth"),
    ]

    for checkbox in checkboxes:
        if checkbox.widget_id != selected_id:
            await checkbox.set_checked(event=event, checked=False, manager=manager)
        else:
            await checkbox.set_checked(event=event, checked=True, manager=manager)

    selected_search = {
        "full_name": "full_name",
        "orcid": "orcid",
        "keywords_auth": "keywords",
    }.get(selected_id, "full_name")

    await manager.update(data={"selected_type": selected_search})


async def document_download_type(event, widget, manager: DialogManager, *args, **kwargs):
    selected_id = widget.widget_id

    checkboxes = [
        manager.dialog().find("ris"),
        manager.dialog().find("csv"),
    ]

    for checkbox in checkboxes:
        if checkbox.widget_id != selected_id:
            await checkbox.set_checked(event=event, checked=False, manager=manager)
        else:
            await checkbox.set_checked(event=event, checked=True, manager=manager)

    selected_download_type = {
        "ris": "ris",
        "csv": "csv",
    }.get(selected_id, "ris")

    await manager.update(data={"selected_download_type": selected_download_type})


async def set_not_pressed_author(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.dialog_data['pressed'] = False
    manager.dialog_data['pressed_new'] = False
    selected_type = manager.dialog_data.get("selected_type")
    
    # Переходим к состояниям в зависимости от выбранного типа
    if selected_type == "full_name":
        await manager.switch_to(FSMGeneral.full_name)
    elif selected_type == "orcid":
        await manager.switch_to(FSMGeneral.orcid)
    else:
        await manager.switch_to(FSMGeneral.keywords)


async def final_auth_dialog(event, source, manager: DialogManager, *args, **kwargs):
    await manager.switch_to(FSMGeneral.validate_auth)


async def next_and_set_not_pressed(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.dialog_data['pressed'] = False
    manager.dialog_data['pressed_new'] = False

    await manager.next()


async def error(
        message: Message,
        dialog_: Any,
        manager: DialogManager,
        error_: ValueError
):
    await message.answer("Необходимо ввести ровно 2 упорядоченных неотрицательных числа через пробел, оба не больше 9999")


def check_years(text):
    num_words = len(text.split())
    if num_words != 2:
        raise ValueError
    words = text.split()
    if not (words[0].isnumeric() and words[1].isnumeric() and int(words[1]) >= int(words[0]) >= 0 and int(words[1]) < 10000):
        raise ValueError
    return text


async def go_to_beginning(callback: CallbackQuery, button: Button, manager: DialogManager):
    await manager.switch_to(FSMGeneral.choose_search)  


async def start_search_pubs(callback: CallbackQuery, button: Button, manager: DialogManager):
    await charge_request(str(callback.message.chat.id))
    manager.dialog_data['folder_id'] = uuid.uuid4()
    manager.dialog_data['pressed'] = True

    await callback.message.answer("Отлично! Теперь, пожалуйста, подождите. Наш бот уже выполняет ваш запрос. Это займет около минуты. ⏳")

    url = "https://scopus.baixo.keenetic.pro:8443/pub/search"
    query = await dialog_get_data(manager)
    query["username"] = callback.from_user.username
    query["user_id"] = callback.from_user.id
    data = {
            "filters_dct": query,
            "folder_id": str(manager.dialog_data['folder_id']),
            "verification": "example_verification"
        }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, ssl=False) as response:
            stat = await get_current_status(manager.dialog_data['folder_id'], 1, 10)
            if stat:
                url = f"https://scopus.baixo.keenetic.pro:8443/result/{manager.dialog_data['folder_id']}"

                async with session.get(url, ssl=False) as resp:
                    respData = await resp.json()
                    result = respData.get('result')
            else:
                await callback.message.answer(text="По Вашему запросу не было найдено ни одной статьи.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
                await manager.done()
                return

    if result[0]:
        manager.dialog_data['pubs_found'] = result[1]
        manager.dialog_data['newest'] = result[2]
        manager.dialog_data['oldest'] = result[3]
        manager.dialog_data['most_cited'] = result[4]
        manager.dialog_data['active_array'] = result[2]

        for i in range(len(result[2])):
            manager.find(f"pub_{i}").text = Const(str(i + 1) + ". " + str(result[2][i]["Title"]))
        await manager.switch_to(state=FSMGeneral.check_pubs, show_mode=ShowMode.SEND)

    else:
        await callback.message.answer(text="По Вашему запросу не было найдено ни одной статьи.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
        await manager.done()


async def start_search_auth(callback: CallbackQuery, button: Button, manager: DialogManager):
    try:
        await charge_request(str(callback.message.chat.id))
        result = []
        manager.dialog_data['doc_count_max'] = None
        manager.dialog_data['active_array'] = None
        manager.dialog_data['folder_id'] = uuid.uuid4()
        manager.dialog_data['pressed'] = True
        #callback.message.chat.id

        await callback.message.answer("Отлично! Теперь, пожалуйста, подождите. Наш бот уже выполняет ваш запрос. Это займет от 30 до 90 секунд. ⏳")

        flag = asyncio.Event()
        future = asyncio.Future()
        manager.dialog_data['future'] = future
        # asyncio.create_task(search_for_author_cred(await dialog_authors(manager), manager.dialog_data['folder_id'], flag, future, manager.dialog_data["selected_type"]))
        # await flag.wait()
        flag.clear()
        manager.dialog_data['flag'] = flag
        url = "https://scopus.baixo.keenetic.pro:8443/auth/search"
        filters = await dialog_authors(manager)
        filters["username"] = callback.from_user.username
        filters["user_id"] = callback.from_user.id
        data = {
            "filters_dct": filters,
            "folder_id": str(manager.dialog_data['folder_id']),
            "search_type": filters['auth_search_type'],
            "verification": "example_verification"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, ssl=False) as response:
                stat = await get_current_status(manager.dialog_data['folder_id'], 1, 10)
                if stat:
                    url = f"https://scopus.baixo.keenetic.pro:8443/result/{manager.dialog_data['folder_id']}"

                    async with session.get(url, ssl=False) as resp:
                        respData = await resp.json()
                        result = respData.get('result')
                else:
                    await callback.message.answer(text="По Вашему запросу не было найдено ни одного автора.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
                    await manager.done()
                    return

        if result[0] or manager.dialog_data.get("selected_type") == "keywords":
            for i in range(50):
                manager.find(str(i)).text = Const("-")
            for i in range(50):
                manager.find(f"key_{i}").text = Const("-")
                    

            if manager.dialog_data.get("selected_type") == "orcid":
                manager.dialog_data['doc_count_max'] = result[1]
                manager.dialog_data['active_array'] = result[1]
                await process_auth_click(callback=callback, button=button, manager=manager)
                await manager.done()

            elif manager.dialog_data.get("selected_type") == "full_name":
                manager.dialog_data['doc_count_max'] = result[1]
                manager.dialog_data['active_array'] = result[1]
                manager.dialog_data['doc_count_low'] = result[2]
                manager.dialog_data['hindex_max'] = result[3]
                manager.dialog_data['hindex_low'] = result[4]
                manager.dialog_data['author_a'] = result[5]
                manager.dialog_data['author_z'] = result[6]
                manager.dialog_data['affil_a'] = result[7]
                manager.dialog_data['affil_z'] = result[8]

                for i in range(len(result[1])):
                    manager.find(str(i)).text = Const(str(i + 1) + ". " + str(result[1][i]["Author"]) + " | " + str(result[1][i]["Documents"]) + " | " + str(result[1][i]["Affiliation"]))
                await manager.switch_to(state=FSMGeneral.check_auths, show_mode=ShowMode.SEND)
                # await manager.update()

            elif manager.dialog_data.get("selected_type") == "keywords":
                try:
                    manager.dialog_data['match_doc_max'] = result[1]
                    manager.dialog_data['active_array'] = result[1]
                    manager.dialog_data['match_doc_low'] = result[2]
                    manager.dialog_data['high_cite'] = result[3]
                    manager.dialog_data['low_cite'] = result[4]
                    manager.dialog_data['total_doc_max'] = result[5]
                    manager.dialog_data['total_doc_low'] = result[6]
                    manager.dialog_data['hindex_max_key'] = result[7]
                    manager.dialog_data['hindex_low_key'] = result[8]
                    for i in range(len(result[1])):
                        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(result[1][i]["Author"]) + " | " + str(result[1][i]["Documents"]) + " | " + str(result[1][i]["Affiliation"]))
                    await manager.switch_to(state=FSMGeneral.check_auths_key, show_mode=ShowMode.SEND)
                    # await manager.update()
                except:
                    traceback.print_exc()


        else:
            traceback.print_exc()
            await callback.message.answer(text="По Вашему запросу не было найдено ни одного автора.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
            await manager.done()
    except:
        traceback.print_exc()
        await callback.message.answer(text="По Вашему запросу не было найдено ни одного автора.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
        await manager.done()


def chunkstring(string, length):
    return [string[0 + i:length + i] for i in range(0, len(string), length)]


async def process_pub_click(callback: CallbackQuery, button: Button, manager: DialogManager):
    ind = int(callback.data.split("_")[-1])
    if ind < len(manager.dialog_data['active_array']):
        list_to_print = chunkstring(f"""
        {ind + 1}
*Название*    
        {manager.dialog_data['active_array'][ind]['Title'].replace('_', '-').replace('*', '✵')}

*Абстракт*
        {manager.dialog_data['active_array'][ind]['Abstract'].replace('_', '-').replace('*', '✵')}

*Авторы*
        {manager.dialog_data['active_array'][ind]['Authors'].replace('_', '-').replace('*', '✵')}

*Источник*
        {manager.dialog_data['active_array'][ind]['Source'].replace('_', '-').replace('*', '✵')}

*Год*
        {manager.dialog_data['active_array'][ind]['Year'].replace('_', '-').replace('*', '✵')}

*Кол-во цитированиий*
        {manager.dialog_data['active_array'][ind]['Citations'].replace('_', '-').replace('*', '✵')  }

\nЧтобы виджет с выбором статей опустился вниз диалога, отправьте любое сообщение. ⬇️

        """, 4096)
        for j in range(len(list_to_print)):
            await callback.message.answer(list_to_print[j], parse_mode='Markdown')
        await manager.switch_to(state=FSMGeneral.check_pubs)


def pub_buttons_create():
    buttons = [Button(Const('-'), id=f"pub_{i}", on_click=process_pub_click, when=~F["pressed_new"]) for i in range(50)]
    return buttons


def auth_buttons_create():
    buttons = [Button(Const('-'), id=f"auth_{i}", on_click=process_auth_click, when=~F["pressed_new"]) for i in range(50)]
    return buttons


def auth_buttons_create_key():
    buttons = [Button(Const('-'), id=f"key_{i}", on_click=process_auth_click, when=~F["pressed_new"]) for i in range(50)]
    return buttons


async def process_auth_click(callback: CallbackQuery, button: Button, manager: DialogManager):
    mes = await button.text.render_text(data=manager.current_context().dialog_data, manager=manager)
    if mes != "-":
        result = []
        
        url = "https://scopus.baixo.keenetic.pro:8443/auth/search/specific"
        if manager.dialog_data['selected_type'] != "orcid":
            await callback.message.answer("Автор выбран! Теперь, пожалуйста, подождите. Наш бот уже выполняет ваш запрос. Это займет некоторое время. ⏳")

        button_id = ""
        if manager.dialog_data.get("selected_type") != "orcid":
            text = await button.text.render_text(data=manager.current_context().dialog_data, manager=manager)
            
        else:
            text = "1"

        if text != "-":
            if manager.dialog_data.get("selected_type") != "orcid":
                if text[1] == ".":
                    button_id = text[0]
                else:
                    button_id = text[:2]
            else:
                button_id = "1"
            data = {
                "folder_id": str(manager.dialog_data['folder_id']),
                "author_id": str(manager.dialog_data['active_array'][int(button_id)-1]["AuthorID"]),
                "verification": "example_verification"
            }
            response = requests.post(url, json=data, verify=False)
        
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, ssl=False) as response:
                    stat = await get_current_status(manager.dialog_data['folder_id'], 1, 30)
                    if stat:

                        url_files = f"https://scopus.baixo.keenetic.pro:8443/auth/get/files/{manager.dialog_data['folder_id']}"
                        files_path = "scopus_files/" + str(manager.dialog_data['folder_id'])
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        folder_path = os.path.join(current_dir, files_path)
                        media = []
                        csv_file = None
                        ris_file = None

                        async with aiohttp.ClientSession() as session:
                            async with session.get(url_files, ssl=False) as response:
                                if response.status == 200:
                                    content = await response.read()
                                    with zipfile.ZipFile(BytesIO(content)) as archive:
                                        archive.extractall(folder_path)

                        all_files = os.listdir(folder_path)

                        photo_files = [
                            f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))
                        ]
                        csv_file = next((f for f in all_files if f.lower().endswith('.csv')), None)
                        ris_file = next((f for f in all_files if f.lower().endswith('.ris')), None)

                        for photo_file in photo_files:
                            photo_path = os.path.join(folder_path, photo_file)
                            media_item = InputMediaPhoto(media=FSInputFile(photo_path))
                            media.append(media_item)


                        if media:
                            await callback.message.answer_media_group(media=media)
                        else:
                            await callback.message.answer("Нет сохранённых графиков.")

                        if csv_file:
                            csv_path = os.path.join(folder_path, csv_file)
                            await callback.message.answer_document(FSInputFile(csv_path))

                        if ris_file:
                            ris_path = os.path.join(folder_path, ris_file)
                            await callback.message.answer_document(FSInputFile(ris_path))

                        if not csv_file and not ris_file:
                            await callback.message.answer("Нет сохранённых файлов.")
                        try:
                            url = f"https://scopus.baixo.keenetic.pro:8443/result/{manager.dialog_data['folder_id']}"

                            response = requests.get(url, verify=False)
                            respData = response.json()
                            
                            result = respData.get('result')
                        except:
                            print(traceback.print_exc())
                    else:
                        await callback.message.answer(text="По Вашему запросу не было найдено ни одного автора.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
                        await manager.done()
                        return

                

        if not result[0]:
            await callback.message.answer("Произошла ошибка при обработке данных.")
            await manager.done()
            return

        author_info = result[0]
        co_authors = result[1]

        await asyncio.sleep(2)

        output_message = "📊 Информация об авторе:\n\n"
        output_message += f"Цитирования: {author_info.get('citations', 'Неизвестно')}\n"
        output_message += f"Документы: {author_info.get('documents', 'Неизвестно')}\n"
        output_message += f"h-индекс: {author_info.get('h_index', 'Неизвестно')}\n\n"

        output_message += "👥 Соавторы:\n\n"
        for co_author in co_authors:
            if co_author['id'] != "-":
                output_message += f"- Имя:  {co_author['name']},   Документы:  {co_author['documents']},  ORCID:  {co_author['id']}\n"
            else:
                output_message += f"- Имя:  {co_author['name']},   Документы:  {co_author['documents']}\n"

        await callback.message.answer(output_message)
        await callback.message.answer("Спасибо, что воспользовались нашим ботом! 🎉\nЧтобы начать новый поиск, напишите команду /search")
        await manager.done()


async def download_file(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.dialog_data['pressed_new'] = True
    folder_path = f"{PROJECT_DIR}/scopus_files/{manager.dialog_data['folder_id']}"
    file_path = f"{folder_path}/scopus.ris"
    url = f"https://scopus.baixo.keenetic.pro:8443/pub/download/files/{manager.dialog_data['selected_download_type']}/{manager.dialog_data['folder_id']}"
    
    try:
        await callback.message.answer("Отлично! Подождите, пожалуйста, пока мы скачиваем файл — это может занять некоторое время. ⏳")
        async with aiohttp.ClientSession() as session:
                async with session.post(url, ssl=False) as response:
                    stat = await get_current_status(manager.dialog_data['folder_id'], 2, 30)
                    if stat:
                        url_files = f"https://scopus.baixo.keenetic.pro:8443/pub/get/files/{manager.dialog_data['selected_download_type']}/{manager.dialog_data['folder_id']}"

                        # Создаем директорию, если она не существует
                        os.makedirs(folder_path, exist_ok=True)

                        # Асинхронный запрос к серверу для загрузки файла
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url_files, ssl=False) as response:
                                if response.status == 200:
                                    with open(file_path, 'wb') as f:
                                        while True:
                                            chunk = await response.content.read(1024)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                else:
                                    await callback.message.answer("Не удалось загрузить файл. Пожалуйста, попробуйте позже.")
                                    return

                        # Отправляем файл пользователю
                        await callback.message.answer_document(document=FSInputFile(file_path))
                        await callback.message.answer("Спасибо, что воспользовались нашим ботом! 🎉\nЧтобы начать новый поиск, напишите команду /search")

                    else:
                        await callback.message.answer(text="По Вашему запросу не было найдено ни одной статьи.\n\nСпасибо, что воспользовались нашим ботом! 🎉\n\nЧтобы искать снова, напишите команду /search")
                        await manager.done()
                        return

    except Exception as e:
        await callback.message.answer("Произошла ошибка, скорее всего, Scopus начудил.\n\nМы не спишем вам запрос. Попробуйте заново или переформулируйте запрос.")
        chat_id = str(callback.message.chat.id)
        add_requests_error(chat_id, 1)
        print(e)
        traceback.print_exc()

        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

    finally:
        await manager.done()


async def sort_by_newest(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("cit").text = Const("⚪️ Cited")
    manager.find("date_new").text = Const("🔘 Newest")
    manager.find("date_old").text = Const("⚪️ Oldest")

    manager.dialog_data['active_array'] = manager.dialog_data['most_cited']

    for i in range(len(manager.dialog_data['newest'])):
        manager.find(f"pub_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['newest'][i]["Title"]))
    manager.dialog_data['active_array'] = manager.dialog_data['newest']   


async def sort_by_oldest(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("cit").text = Const("⚪️ Cited")
    manager.find("date_new").text = Const("⚪️ Newest")
    manager.find("date_old").text = Const("🔘 Oldest")

    manager.dialog_data['active_array'] = manager.dialog_data['most_cited']

    for i in range(len(manager.dialog_data['oldest'])):
        manager.find(f"pub_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['oldest'][i]["Title"])) 
    manager.dialog_data['active_array'] = manager.dialog_data['oldest']  


async def sort_by_most_cited(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("cit").text = Const("🔘 Cited")
    manager.find("date_new").text = Const("⚪️ Newest")
    manager.find("date_old").text = Const("⚪️ Oldest")

    manager.dialog_data['active_array'] = manager.dialog_data['most_cited']

    for i in range(len(manager.dialog_data['most_cited'])):
        manager.find(f"pub_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['most_cited'][i]["Title"]))  
    manager.dialog_data['active_array'] = manager.dialog_data['most_cited'] 


async def sort_by_doc_count_max(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("🔘 Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['doc_count_max'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['doc_count_max'][i]["Author"]) + " | " + str(manager.dialog_data['doc_count_max'][i]["Documents"]) + " | " + str(manager.dialog_data['doc_count_max'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']


async def sort_by_doc_count_low(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("🔘 Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['doc_count_low'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['doc_count_low'][i]["Author"]) + " | " + str(manager.dialog_data['doc_count_low'][i]["Documents"]) + " | " + str(manager.dialog_data['doc_count_low'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_low']


async def sort_by_h_index_max(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("🔘 H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['hindex_max'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['hindex_max'][i]["Author"]) + " | " + str(manager.dialog_data['hindex_max'][i]["Documents"]) + " | " + str(manager.dialog_data['hindex_max'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['hindex_max']


async def sort_by_h_index_low(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("🔘 H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['hindex_low'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['hindex_low'][i]["Author"]) + " | " + str(manager.dialog_data['hindex_low'][i]["Documents"]) + " | " + str(manager.dialog_data['hindex_low'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['hindex_low']


async def sort_by_author_a(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("🔘 Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['author_a'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['author_a'][i]["Author"]) + " | " + str(manager.dialog_data['author_a'][i]["Documents"]) + " | " + str(manager.dialog_data['author_a'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['author_a']


async def sort_by_author_z(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("🔘 Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['author_z'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['author_z'][i]["Author"]) + " | " + str(manager.dialog_data['author_z'][i]["Documents"]) + " | " + str(manager.dialog_data['author_z'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['author_z']


async def sort_by_affil_a(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("🔘 Affiliation (A-Z)")
    manager.find("affil_z").text = Const("⚪️ Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['affil_a'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['affil_a'][i]["Author"]) + " | " + str(manager.dialog_data['affil_a'][i]["Documents"]) + " | " + str(manager.dialog_data['affil_a'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['affil_a']


async def sort_by_affil_z(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("doc_count_max").text = Const("⚪️ Doc Count (max)")
    manager.find("doc_count_low").text = Const("⚪️ Doc Count (low)")
    manager.find("hindex_max").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low").text = Const("⚪️ H-index (low)")
    manager.find("author_a").text = Const("⚪️ Author (A-Z)")
    manager.find("author_z").text = Const("⚪️ Author (Z-A)")
    manager.find("affil_a").text = Const("⚪️ Affiliation (A-Z)")
    manager.find("affil_z").text = Const("🔘 Affiliation (Z-A)")
    


    manager.dialog_data['active_array'] = manager.dialog_data['doc_count_max']

    for i in range(len(manager.dialog_data['affil_z'])):
        manager.find(str(i)).text = Const(str(i + 1) + ". " + str(manager.dialog_data['affil_z'][i]["Author"]) + " | " + str(manager.dialog_data['affil_z'][i]["Documents"]) + " | " + str(manager.dialog_data['affil_z'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['affil_z']


async def sort_by_match_doc_max(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("🔘 Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['match_doc_max'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['match_doc_max'][i]["Author"]) + " | " + str(manager.dialog_data['match_doc_max'][i]["Documents"]) + " | " + str(manager.dialog_data['match_doc_max'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']


async def sort_by_match_doc_low(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("🔘 Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['match_doc_low'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['match_doc_low'][i]["Author"]) + " | " + str(manager.dialog_data['match_doc_low'][i]["Documents"]) + " | " + str(manager.dialog_data['match_doc_low'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_low']


async def sort_by_high_cite(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("🔘 Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['high_cite'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['high_cite'][i]["Author"]) + " | " + str(manager.dialog_data['high_cite'][i]["Documents"]) + " | " + str(manager.dialog_data['high_cite'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['high_cite']


async def sort_by_low_cite(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("🔘 Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['low_cite'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['low_cite'][i]["Author"]) + " | " + str(manager.dialog_data['low_cite'][i]["Documents"]) + " | " + str(manager.dialog_data['low_cite'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['low_cite']


async def sort_by_total_doc_max(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("🔘 Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['total_doc_max'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['total_doc_max'][i]["Author"]) + " | " + str(manager.dialog_data['total_doc_max'][i]["Documents"]) + " | " + str(manager.dialog_data['total_doc_max'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['total_doc_max']


async def sort_by_total_doc_low(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("🔘 Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['total_doc_low'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['total_doc_low'][i]["Author"]) + " | " + str(manager.dialog_data['total_doc_low'][i]["Documents"]) + " | " + str(manager.dialog_data['total_doc_low'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['total_doc_low']


async def sort_by_hindex_max(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("🔘 H-index (max)")
    manager.find("hindex_low_key").text = Const("⚪️ H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['hindex_max_key'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['hindex_max_key'][i]["Author"]) + " | " + str(manager.dialog_data['hindex_max_key'][i]["Documents"]) + " | " + str(manager.dialog_data['hindex_max_key'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['hindex_max_key']


async def sort_by_hindex_low(callback: CallbackQuery, button: Button, manager: DialogManager):
    manager.find("match_doc_max").text = Const("⚪️ Match Docs (max)")
    manager.find("match_doc_low").text = Const("⚪️ Match Docs (low)")
    manager.find("high_cite").text = Const("⚪️ Total Citations (max)")
    manager.find("low_cite").text = Const("⚪️ Total Citations (low)")
    manager.find("total_doc_max").text = Const("⚪️ Total Docs (max)")
    manager.find("total_doc_low").text = Const("⚪️ Total citations (low)")
    manager.find("hindex_max_key").text = Const("⚪️ H-index (max)")
    manager.find("hindex_low_key").text = Const("🔘 H-index (low)")

    manager.dialog_data['active_array'] = manager.dialog_data['match_doc_max']

    for i in range(len(manager.dialog_data['hindex_low_key'])):
        manager.find(f"key_{i}").text = Const(str(i + 1) + ". " + str(manager.dialog_data['hindex_low_key'][i]["Author"]) + " | " + str(manager.dialog_data['hindex_low_key'][i]["Documents"]) + " | " + str(manager.dialog_data['hindex_low_key'][i]["Affiliation"]))
    manager.dialog_data['active_array'] = manager.dialog_data['hindex_low_key']


main_menu = Dialog(
    Window(
        Const(
            "Выберите, что ищем: статью или автора. 🔍"
        ),
        Row(
            Checkbox(
                Const("☑️ 📄 Статья"),
                Const("⬜ 📄 Статья"),
                id="article",
                default=False,
                on_click=on_checkbox_search,
            ),
            Checkbox(
                Const("☑️ 👤 Автор"),
                Const("⬜ 👤 Автор"),
                id="author",
                default=False,
                on_click=on_checkbox_search,
            )
        ),
        Button(text=Const("➡️ Дальше"), id="save", on_click=choose_search_type),
        state=FSMGeneral.choose_search
    ),
    Window(
        Const(
            "Выберите, если нужно, языки для фильтрации публикаций. 🌐"
        ),
        Row(
            Checkbox(
                Const("☑️ 🇷🇺 Русский"),
                Const("⬜ 🇷🇺 Русский"),
                id="ru",
                default=False,  # so it will be checked by default,
            ),
            Checkbox(
                Const("☑️ 🇬🇧 Английский"),
                Const("⬜ 🇬🇧 Английский"),
                id="eng",
                default=False,  # so it will be checked by default,
            ),
        ),
        Button(text=Const("➡️ Дальше"), id="save", on_click=next_and_set_not_pressed),
        state=FSMGeneral.choose_language,
    ),
    Window(
        Const(
            "Укажите временной диапазон, в котором Вы хотите искать статьи, введя годы через пробел. 📅\n\nНапример:\n0 2028 или 1989 2001 или 2023 2023"
        ),
        TextInput(
            id="years",
            on_error=error,
            on_success=Next(),
            type_factory=check_years,
        ),
        state=FSMGeneral.choose_years,
    ),
    Window(
        Const(
            "Выберите типы документов для фильтрации (если необходимо):"
        ),
        Row(
            Checkbox(
                Const("☑️ 📝 Статья (Article)"),
                Const("⬜ 📝 Статья (Article)"),
                id="art",
                default=False,  # so it will be checked by default,
            ),
            Checkbox(
                Const("☑️ 📢 Обзор (Review)"),
                Const("⬜ 📢 Обзор (Review)"),
                id="rev",
                default=False,  # so it will be checked by default,
            ),
        ),
        Row(
            Checkbox(
                Const("☑️ 👥 Статья с конференции\n(Conference Paper)"),
                Const("⬜ 👥 Статья с конференции\n(Conference Paper)"),
                id="conf",
                default=False,  # so it will be checked by default,
            ),
        ),
        Button(text=Const("➡️ Дальше"), id="save", on_click=Next()),
        state=FSMGeneral.choose_document_type,
    ),
    Window(
        Const(
            "📋 Выберите тип фильтрации (стандартное значение — Title-abs-key), если требуется другой:"
        ),
        Row(
            Checkbox(
                Const("☑️ Title-abs-key"),
                Const("⬜ Title-abs-key"),
                id="tak",
                default=False,  # so it will be checked by default,
                on_click=on_checkbox_click_pubs,
            ),
        ),
        Row(
            Checkbox(
                Const("☑️ Title"),
                Const("⬜ Title"),
                id="title",
                default=False,  # so it will be checked by default,
                on_click=on_checkbox_click_pubs,
            ),
            Checkbox(
                Const("☑️ Keywords"),
                Const("⬜ Keywords"),
                id="keywords",
                default=False,  # so it will be checked by default,
                on_click=on_checkbox_click_pubs,
            ),
            Checkbox(
                Const("☑️ Authors"),
                Const("⬜ Authors"),
                id="authors",
                default=False,  # so it will be checked by default,
                on_click=on_checkbox_click_pubs,
            ),
        ),
        Button(text=Const("➡️ Дальше"), id="save", on_click=Next()),
        state=FSMGeneral.choose_filter_type,
    ),
    Window(
        Const("Пожалуйста, введите сам поисковый запрос. 🔍"),
        TextInput(
            id="query",
            on_success=Next(),
        ),
        state=FSMGeneral.filling_query,
    ),
    Window(
        Format(
        """Запрос успешно сформирован!\n\nПроверьте корректность введённых данных — если есть опечатки, результат может отсутствовать, а запрос будет списан. 🧐

    Русский язык: {ru}
    Английский язык: {eng}
    Года: {years}
    Article: {art}
    Review: {rev}
    Conference paper: {conf}
    Фильтр: {filter_type}
    ----------------
    Текст запроса: "{query}" 
    """),
        Button(text=Const("🔁 Заново"), id="again", on_click=go_to_beginning, when=~F["pressed"]),
        Button(text=Const("▶️ Поиск"), id="search", on_click=start_search_pubs, when=~F["pressed"]),
        state=FSMGeneral.validate_pubs,
        getter=dialog_get_data  # here we specify data getter for dialog
    ),
    Window(
        Row (
            Button(text=Const("⚪️ Cited"), id="cit", on_click=sort_by_most_cited),
            Button(text=Const("🔘 Newest"), id="date_new", on_click=sort_by_newest),
            Button(text=Const("⚪️ Oldest"), id="date_old", on_click=sort_by_oldest)
        ),
        Format("По вашему запросу найдено {pubs_found} статей.\n\n Ниже представлен топ соответствующих."),
        ScrollingGroup(
            *pub_buttons_create(),
            id="numbers",
            width=1,
            height=8,
        ),
        Button(text=Const("Скачать файл со всеми статьями 👑"), id="choose_download_type", on_click=Next()),
        #Button(text=Const("Не скачивать файл"), id="do_not_download", on_click=do_not_download_file, when=~F["pressed_new"]),
        state=FSMGeneral.check_pubs,
        getter=pubs_found
    ),
    Window(
        Const(
            "Выберите тип файла: CSV или RIS."
        ),
        Row(
            Checkbox(
                Const("☑️ CSV"),
                Const("⬜ CSV"),
                id="csv",
                default=False,  # so it will be checked by default,
                on_click=document_download_type,
            ),
            Checkbox(
                Const("☑️ RIS"),
                Const("⬜ RIS"),
                id="ris",
                default=True,  # so it will be checked by default,
                on_click=document_download_type,
            ),
        ),
        Button(text=Const("Скачать файл со всеми статьями 👑"), id="download", on_click=download_file, when=~F["pressed_new"]),
        state=FSMGeneral.choose_download_type,
    ),
    Window(
        Const(
            "Выберите тип поиска: по имени или по ORCID. 🔍"
        ),
        Row(
            Checkbox(
                Const("☑️ 👤 Фамилия, имя"),
                Const("⬜ 👤 Фамилия, имя"),
                id="full_name",
                default=False,  # so it will be checked by default,
                on_click=author_search_type,
            ),
            Checkbox(
                Const("☑️ 🆔 ORCID"),
                Const("⬜ 🆔 ORCID"),
                id="orcid",
                default=False,  # so it will be checked by default,
                on_click=author_search_type,
            ),
        ),
        Row(
            Checkbox(
                Const("☑️ 🔑 Keywords"),
                Const("⬜ 🔑 Keywords"),
                id="keywords_auth",
                default=False,  # so it will be checked by default,
                on_click=author_search_type,
            ),
        ),
        Button(text=Const("➡️ Дальше"), id="save", on_click=set_not_pressed_author),
        state=FSMGeneral.name_or_orcid,
    ),
    Window(
        Const("Пожалуйста, введите фамилию и имя через пробел. 🔍"),
        TextInput(
            id="name_search",
            on_success=final_auth_dialog,
        ),
        state=FSMGeneral.full_name,
    ),
    Window(
        Const("Пожалуйста, введите ORCID. 🔍"),
        TextInput(
            id="orcid_search",
            on_success=final_auth_dialog,
        ),
        state=FSMGeneral.orcid,
    ),
    Window(
        Const("Пожалуйста, введите Keywords. 🔍"),
        TextInput(
            id="keywords_auth_search",
            on_success=final_auth_dialog,
        ),
        state=FSMGeneral.keywords,
    ),
    Window(
        Format(
        """Запрос успешно сформирован! ✅\n\nПроверьте корректность введённых данных — если есть опечатки, результат может отсутствовать, а запрос будет списан. 🧐

    Фильтр: {auth_search_type}
    ----------------
    Текст запроса: "{query}" 
    """),
        Button(text=Const("🔁 Заново"), id="again", on_click=go_to_beginning, when=~F["pressed"]),
        Button(text=Const("▶️ Поиск"), id="search", on_click=start_search_auth, when=~F["pressed"]),
        state=FSMGeneral.validate_auth,
        getter=dialog_authors  # here we specify data getter for dialog
    ),
    Window(
        Row (
            Button(text=Const("🔘 Doc Count (max)"), id="doc_count_max", on_click=sort_by_doc_count_max),
            Button(text=Const("⚪️ Doc Count (low)"), id="doc_count_low", on_click=sort_by_doc_count_low),    
        ),
        Row(
            Button(text=Const("⚪️ H-index (max)"), id="hindex_max", on_click=sort_by_h_index_max),
            Button(text=Const("⚪️ H-index (low)"), id="hindex_low", on_click=sort_by_h_index_low),
        ),
        Row(
            Button(text=Const("⚪️ Author (A-Z)"), id="author_a", on_click=sort_by_author_a),
            Button(text=Const("⚪️ Author (Z-A)"), id="author_z", on_click=sort_by_author_z),
        ),
        Row(
            Button(text=Const("⚪️ Affiliation (A-Z)"), id="affil_a", on_click=sort_by_affil_a),
            Button(text=Const("⚪️ Affiliation (Z-A)"), id="affil_z", on_click=sort_by_affil_z),
        ),
        Format("🔍 По вашему запросу найдены авторы\n\n📋 Рейтинг соответствующих:\n\nФамилия, имя | Количество документов | Учреждение"),
        ScrollingGroup(
            *auth_buttons_create(),
            id="numbers",
            width=1,
            height=8,
        ),
        #Button(text=Const("Скачать файл со всеми статьями 👑"), id="download", on_click=download_file, when=~F["pressed_new"]),
        #Button(text=Const("Не скачивать файл"), id="do_not_download", on_click=do_not_download_file, when=~F["pressed_new"]),
        state=FSMGeneral.check_auths,
        #getter=auths_found
    ),
    Window(
        Row (
            Button(text=Const("🔘 Match Docs (max)"), id="match_doc_max", on_click=sort_by_match_doc_max),
            Button(text=Const("⚪️ Match Docs (low)"), id="match_doc_low", on_click=sort_by_match_doc_low),
        ),
        Row(
            Button(text=Const("⚪️ Total Citations (max)"), id="high_cite", on_click=sort_by_high_cite),
            Button(text=Const("⚪️ Total Citations (low)"), id="low_cite", on_click=sort_by_low_cite),
        ),
        Row(
            Button(text=Const("⚪️ Total Docs (max)"), id="total_doc_max", on_click=sort_by_total_doc_max),
            Button(text=Const("⚪️ Total Docs (low)"), id="total_doc_low", on_click=sort_by_total_doc_low),
        ),
        Row(
            Button(text=Const("⚪️ H-index (max)"), id="hindex_max_key", on_click=sort_by_hindex_max),
            Button(text=Const("⚪️ H-index (low)"), id="hindex_low_key", on_click=sort_by_hindex_low),
        ),
        Format("🔍 По вашему запросу найдены авторы\n\n📋 Рейтинг соответствующих:\n\nФамилия, имя | Количество документов | Учреждение"),
        ScrollingGroup(
            *auth_buttons_create_key(),
            id="numbers_key",
            width=1,
            height=8,
        ),
        #Button(text=Const("Скачать файл со всеми статьями 👑"), id="download", on_click=download_file, when=~F["pressed_new"]),
        #Button(text=Const("Не скачивать файл"), id="do_not_download", on_click=do_not_download_file, when=~F["pressed_new"]),
        state=FSMGeneral.check_auths_key,
        #getter=auths_found
    ),
    
)