import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
import telegram.ext
import exceptions
from dotenv import load_dotenv
from telegram.error import TelegramError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('API_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s %(name)s',
        handlers=[
            logging.FileHandler('main.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)]
    )


def send_message(bot, message: str) -> None:
    """Функция отправки сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправленно.')
    except TelegramError as error:
        logging.error(f'Ошибка при отправке сообщения {error}')


def get_api_answer(current_timestamp: int) -> dict:
    """Функция делает запрос к API и возвращает данные в формате python."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    # Сделали запрос к API
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    # Любой сбой при запросе к эндпоинту
    except Exception as error:
        raise exceptions.ApiError(f'Ошибка API: {error}')

    # Если сервер недоступен
    if response.status_code != HTTPStatus.OK:
        raise exceptions.BadResponse(
            f'Эндпоинт недоступен. Код ответа API: {response.status_code}')

    return response.json()


def check_response(response: list) -> list:
    """Проверка что полученный ответ - это словарь."""
    if isinstance(response['homeworks'], list):
        return response.get('homeworks')
    raise TypeError('Полученный ответ не является словарём.')


def parse_status(homework: dict) -> str:
    """Функция проверяет ответ API и возвращает статус."""
    if 'homework_name' and 'status' in homework:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    else:
        raise exceptions.ApiKeyError(
            'В ответе API отсутсвуют необходимые ключи.')

    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise KeyError('Неизвестный статус ДЗ.')


def check_tokens() -> bool:
    """Функция проверяет что доступны все переменные окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения.')
        raise ValueError

    # Создали бота для отправки сообщения статуса
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    # Текущая временная метка
    current_timestamp = int(time.time())

    # Переменная для сравнения старого и нового ответа
    arch_verdict = ''

    # Переменная для сравнения старой и новой ошибки
    arch_error = ''

    while True:
        try:
            # Сделали запрос к API
            api_response = get_api_answer(current_timestamp)

            # Проверка ответа и получение списка ДЗ
            homeworks_list = check_response(api_response)

            # Проверяю, что ДЗ обновилось
            if homeworks_list:
                # Получить вердикт
                verdict = parse_status(homeworks_list[0])

                # Если вердикт обновился - отправить статус в чат
                if arch_verdict != verdict:
                    send_message(bot, verdict)
                    arch_verdict = verdict
            else:
                logging.debug('В ответе отсутствуют новые статусы.')

            # Переназначаем интервал на время предыдущей попытки
            current_timestamp = api_response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if arch_error != message:
                send_message(bot, message)
                arch_error = message
            else:
                logging.error(f'Ошибка при отправке сообщения {error}')

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
