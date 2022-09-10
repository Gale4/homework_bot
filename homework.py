import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
import telegram.ext
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('API_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s %(name)s',
    handlers=[
        logging.FileHandler('main.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)]
)


def send_message(bot, message):
    """Функция отправки сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправленно.')
    except Exception:
        logging.error('Неудача при отправке сообщения.')


def get_api_answer(current_timestamp):
    """Функция делает запрос к API и возвращает данные в формате python."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    # Сделали запрос к API
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    # Любой сбой при запросе к эндпоинту
    except Exception as error:
        logging.error(
            f'Ошибка API: {error}.')

    # Если сервер недоступен
    if response.status_code != HTTPStatus.OK:
        logging.error(
            f'Эндпоинт недоступен. Код ответа API: {response.status_code}.')
        raise ResourceWarning('Ошибка API сервера.')

    return response.json()


def check_response(response):
    """Проверка что полученный ответ - это словарь."""
    if type(response['homeworks']) == list:
        return response.get('homeworks')
    else:
        logging.error('Полученный ответ не является словарём.')
        raise TypeError('Результат не является словарем.')


def parse_status(homework):
    """Функция получает ответ сервера, проверяет наличие необходимых полей 
    и возвращает сообщение с именем и обновленным статусом.
    """
    if 'homework_name' and 'status' in homework:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    else:
        logging.error('В ответе API отсутсвуют необходимые ключи.')
        raise KeyError

    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logging.error('Неизвестный статус ДЗ.')
        raise KeyError


def check_tokens():
    """Функция проверяет что доступны все переменные окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(tokens)


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        logging.critical('Отсутствуют обязательные переменные окружения.')
        raise ValueError('Нет переменных окружения.')

    # Создали бота для отправки сообщения статуса
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    # Текущая временная метка
    current_timestamp = int(time.time())

    while True:
        try:
            # Сделали запрос к API
            api_response = get_api_answer(current_timestamp)

            # Проверка ответа
            correct_response = check_response(api_response)

            # Получить вердикт
            verdict = parse_status(correct_response[0])

            # Отправка статуса в чат
            send_message(bot, verdict)

            # Переназначаем интервал на время предыдущей попытки
            current_timestamp = api_response.get('current_date')

            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            sys.exit('Неизвестная ошибка.')


if __name__ == '__main__':
    main()
