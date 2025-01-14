import os


REQUESTS_DCT = {
    29: 1,
    149: 5,
    269: 10,
    449: 20,
    999: 300,
    1499: 500,
    1999: 800,
    299: 0,
}

AMOUNTS_DCT = {
    'subscription': 299,
    'button_1': 29,
    'button_5': 149,
    'button_10': 269,
    'button_20': 449,
    'small': 999,
    'medium': 1499,
    'large': 1999,
}

DESCRIPTIONS_DCT = {
    29: "Покупка 1 запроса",
    149: "Покупка 5 запросов",
    269: "Покупка 10 запросов",
    449: "Покупка 20 запросов",
    999: "Покупка 300 запросов",
    1499: "Покупка 500 запросов",
    1999: "Покупка 800 запросов",
    299: "Покупка запросов",
}

FILTERS_DCT = {
    'Title-abstract-keywords': "TITLE-ABS-KEY",
    'Authors': "AUTH",
    'Title': "TITLE",
    'Keywords': "KEY",
    '': "",
}

project_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR= os.path.dirname(project_dir)

MONTHS_DCT = {
    '01': 'января',
    '02': 'февраля',
    '03': 'марта',
    '04': 'апреля',
    '05': 'мая',
    '06': 'июня',
    '07': 'июля',
    '08': 'августа',
    '09': 'сентября',
    '10': 'октября',
    '11': 'ноября',
    '12': 'декабря'
}
