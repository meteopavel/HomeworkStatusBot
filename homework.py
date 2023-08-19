import logging
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import LackOfToken

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandexx.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - '
    '%(funcName)s - '
    '%(lineno)d - '
    '%(name)s - '
    '%(levelname)s - '
    '%(message)s'
)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


def check_tokens() -> bool:
    """Проверить доступность токенов."""
    logger.debug('Начало проверки наличия необходимых токенов')
    required_tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    missing_tokens = [
        token for token in required_tokens if not globals()[token]
    ]
    if missing_tokens:
        logger.critical(f'Следующие токены отсутствуют:\n- {missing_tokens}')
        raise LackOfToken(f'Следующие токены отсутствуют:\n- {missing_tokens}')
    logger.debug('Все необходимые токены в наличии')


def send_message(bot, message):
    """Отправить сообщение."""
    logger.debug('Попытка отправить сообщение')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug(f'Сообщение успешно отправлено \n Текст сообщения: {message}')


def get_api_answer(timestamp) -> str:
    """Получить ответ сервера."""
    try:
        logger.debug('Попытка отправить запрос на сервер')
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        logger.debug('Успешное получение ответа от сервера')
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} с параметрами запроса {params} недоступен'
        ) from error
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Статус эндпоинта отличен от 200 и равен {response.status_code}'
        )
    return response.json()


def check_response(response) -> str:
    """Проверить ответ сервера."""
    logger.debug('Начало проверки ответа сервера')
    if not isinstance(response, dict):
        raise TypeError(
            f'Вместо ожидаемого словаря API вернул тип данных {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError('В словаре, который вернул API, нет ключа `homeworks`')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'В словаре, который вернул API, под ключом `homeworks` содержится '
            f'не список, а другой тип данных: {type(response["homeworks"])}'
        )
    logger.debug('Проверка ответа сервера завершена успешно')


def parse_status(homework) -> str:
    """Распарсить статус работы."""
    logger.debug('Начало парсинга статуса работы')
    if 'homework_name' not in homework:
        raise KeyError(
            'API вернул работу, где отсутствует ожидаемый ключ `homework_name`'
        )
    homework_name = homework['homework_name']
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'API вернул неожиданный статус работы: {homework_status}. '
            f'Ожидался один из следующих вариантов: {HOMEWORK_VERDICTS.keys()}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.debug('Парсинг статуса работы завершён успешно')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    sent_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = response['homeworks']
            check_response(response)
            if not homeworks:
                logger.debug('В работах отсутствует изменение статуса')
                continue
            message = parse_status(homeworks[0])
            if sent_message != message:
                send_message(bot, message)
                sent_message = message
            timestamp = response.get('current_date', timestamp)
        except telegram.error.TelegramError:
            logger.error('Ошибка доступности Telegram')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if sent_message != message:
                with suppress(Exception):
                    send_message(bot, message)
                sent_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
