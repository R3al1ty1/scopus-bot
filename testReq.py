import requests

url = "http://127.0.0.1:8000/auth/search/"
filters = []
print("Тип filters:", type(filters))
print("Содержимое filters:", filters)
print("Тип auth_search_type:", type(filters['auth_search_type']))

# Убедимся, что все ключи и значения верны
if 'auth_search_type' not in filters:
    raise ValueError("Ключ 'auth_search_type' отсутствует в filters")

data = {
    "filters_dct": filters,  # Остается словарем
    "folder_id": "test",  # Преобразуем в строку
    "search_type": "imp",  # Строка из словаря
    "verification": "example_verification"
}

print("Отправляемые данные:", data)

response = requests.post(url, json=data)
print("Статус-код ответа:", response.status_code)
print("Ответ:", response.json())