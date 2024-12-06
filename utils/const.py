import os


REQUESTS_DCT = {
    29: 1,
    149: 5,
    269: 10,
    449: 20,
    999: 300,
    1499: 500,
    1999: 800,
}

AMOUNTS_DCT = {
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
