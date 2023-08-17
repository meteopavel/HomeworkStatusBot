import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import LackOfToken, LackOfNewStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger()
streamHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
streamHandler.setFormatter(formatter)
streamHandler.setLevel(logging.DEBUG)
logger.addHandler(streamHandler)


def check_tokens() -> bool:
    """Проверить доступность токенов."""
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in required_tokens:
        if not token:
            logging.critical(f'Следующие токены отсутствуют:\n- {token}')
            raise LackOfToken(f'Отсутствует необходимый токен {token}')
    return True


def send_message(bot, message):
    """Отправить сообщение."""
    text = message
    chat_id = TELEGRAM_CHAT_ID
    bot.send_message(chat_id, text)
    logging.debug('Сообщение успешно отправлено')


def get_api_answer(timestamp) -> str:
    """Получить ответ сервера."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException:
        logging.error('Эндпоинт недоступен')
        raise ConnectionError
    if response.status_code != HTTPStatus.OK:
        logging.error('Статус эндпоинта отличен от 200')
        raise ConnectionError
    return response.json()


def check_response(response) -> str:
    """Проверить ответ сервера."""
    if response:
        if 'homeworks' not in response:
            logging.error('В ответе API нет ключа `homeworks`')
            raise TypeError('В ответе API нет ключа `homeworks`')
        if not isinstance(response['homeworks'], list):
            logging.error('Под ключом `homeworks` не список')
            raise TypeError('Под ключом `homeworks` не список')
        if not isinstance(response, dict):
            logging.error('API вернул неверную структуру данных')
            raise TypeError('API вернул неверную структуру данных')
        if response['homeworks'] == []:
            logging.debug('В ответе отсутствуют новые статусы')
            raise LackOfNewStatus('В ответе отсутствуют новые статусы')
        return response['homeworks'][0]


def parse_status(homework) -> str:
    """Распарсить статус работы."""
    if 'homework_name' not in homework:
        logging.error('API не вернул домашку')
        raise KeyError('API не вернул домашку')
    homework_name = homework['homework_name']
    if homework['status'] in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise logging.critical('Сбой глобальных переменных')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    # old_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            """
            Пытался реализовать пункт о неотправке
            сообщения об одной и той же ошибке.
            Но мой вариант не проходит тест. Нужна подсказка
            """
            """
            if str(old_error) != str(error):
                old_error = error
                send_message(bot, message)
            """
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
