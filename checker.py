import aiohttp
import asyncio
import datetime
import os

from dotenv import load_dotenv

load_dotenv()

BOT_ADMIN = os.getenv('BOT_ADMIN')
EXPECTED_RESPONSE = {"status": "ok"}
BASE_URL = f"https://api.telegram.org/bot{BOT_ADMIN}/sendMessage"

async def dialog_get_data():

    return {
            "ru": "False",
            "eng": "False",
            "years": "0 2028",
            "art": "True", "rev": "False",
            "conf": "False",
            "filter_type": "Title-abstract-keywords",
            "query": "economics",
            "pressed": "True",
            "username": "tester",
            "user_id": 111111
        }




async def send_message(session, chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        async with session.post(BASE_URL, json=payload) as response:
            if response.status != 200:
                print(f"Ошибка {response.status} при отправке пользователю {chat_id}")
            else:
                print(f"Сообщение отправлено пользователю {chat_id}")
    except Exception as e:
        print(f"Ошибка при отправке пользователю {chat_id}: {e}")


async def get_current_status(folder_id, status_number, retries):
    for i in range(retries):
        await asyncio.sleep(10)
        status_number = str(status_number)
        url = f"https://scopus.baixo.keenetic.pro:8443/status/auto_test_folder_id/{status_number}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=False) as response:
                data = await response.json()
                if data.get('status') == "true":
                    return True
                elif data.get('status') == "failed":
                    return False
    return False


async def check_server_response():
    try:
        url = "https://scopus.baixo.keenetic.pro:8443/pub/search"
        query = await dialog_get_data()
        data = {
                "filters_dct": query,
                "folder_id": 'auto_test_folder_id',
                "verification": "example_verification"
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, ssl=False) as response:
                stat = await get_current_status('auto_test_folder_id', 1, 10)
                if stat:
                    url = f"https://scopus.baixo.keenetic.pro:8443/result/auto_test_folder_id"

                    async with session.get(url, ssl=False) as resp:
                        respData = await resp.json()
                        result = respData.get('result')
                        try:
                            if result and result[0] == "true":
                                return True
                            else:
                                return False
                        except:
                            return False

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        return False


async def run_periodically():
    cnt = 0
    max_attempts = 3
    attempts = 0

    while True:
        result = await check_server_response()
        if result:
            print(f"{datetime.datetime.now()} Запрос номер {cnt}, функция вернула True.")
            attempts = 0
        else:
            attempts += 1
            print(f"{datetime.datetime.now()} Попытка {cnt} неудачная.")
            for i in range(2):
                res = await check_server_response()
                if not res:
                    attempts += 1
                else:
                    attempts = 0
                    break
            if attempts >= max_attempts:
                print("Функция не вернула True за 3 попытки.")
                async with aiohttp.ClientSession() as session_http:
                    await send_message(session_http, 458920125, 'сервак отвалился')
                attempts = 0
        cnt += 1
        await asyncio.sleep(1800)


async def main():
    await run_periodically()

if __name__ == "__main__":
    asyncio.run(main())
