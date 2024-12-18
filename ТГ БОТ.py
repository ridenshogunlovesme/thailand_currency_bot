from aiogram import Bot, Dispatcher, executor, types
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

TOKEN = '7602200094:AAGxZh24TBmuofCn1sIlSK9i96-6hY8oOuc'

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Состояния для хранения суммы в рублях
class Form(StatesGroup):
    amount = State()

# 1. Вставьте здесь функцию для создания кнопки ввода суммы
def get_amount_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Ввести сумму", callback_data='enter_amount'))
    return keyboard

# 2. Вставьте здесь обработчик команды /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Пожалуйста, введите сумму для конвертации:", reply_markup=get_amount_keyboard())

# 3. Вставьте здесь обработчик нажатия на кнопку "Ввести сумму"
@dp.callback_query_handler(lambda c: c.data == 'enter_amount')
async def process_enter_amount(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Введите сумму в рублях:")

# 4. Вставьте здесь обработчик ввода суммы
@dp.message_handler(lambda message: message.text.isdigit())
async def process_amount_input(message: types.Message):
    amount = int(message.text)
    # Сохраните сумму в контексте или состоянии пользователя
    # Затем предложите выбор валют для конвертации
    await message.reply("Выберите вариант конвертации:", reply_markup=get_currency_keyboard())

# 5. Вставьте здесь функцию для создания кнопок выбора валют
def get_currency_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Рубль-Доллар-Бат", callback_data='rub_usd_bat'))
    keyboard.add(InlineKeyboardButton("Рубль-Евро-Бат", callback_data='rub_eur_bat'))
    keyboard.add(InlineKeyboardButton("Рубль-Юань-Бат", callback_data='rub_cny_bat'))
    keyboard.add(InlineKeyboardButton("Рубль-Бат", callback_data='rub_bat'))
    keyboard.add(InlineKeyboardButton("Все варианты", callback_data='all_variants'))
    return keyboard


def get_currency_rates(url):
    """Получает курсы всех валют с сайта myfin.by с помощью BeautifulSoup."""
    try:
        # Отправляем GET-запрос к указанному URL
        response = requests.get(url)
        response.raise_for_status()  # Проверяем, что запрос успешен

        # Создаем объект BeautifulSoup для парсинга HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Находим таблицу с курсами
        rates_table = soup.find("table", class_="table-best yellow_bg")

        if rates_table is None:
            print("Таблица с курсами не найдена.")
            return None, None, None

        rates = {}
        # Находим строки таблицы
        rows = rates_table.find_all("tr")

        # Сбор данных из всех строк таблицы
        for row in rows:
            columns = row.find_all("td")
            if len(columns) > 0:
                # Извлекаем название валюты
                currency_name_element = columns[0].find(class_="title")
                currency_name = (
                    currency_name_element.text.strip()
                    if currency_name_element
                    else columns[0].text.strip()
                )

                buy_rate = columns[1].text.strip()  # Курс покупки
                try:
                    buy_rate_value = float(
                        buy_rate.replace(",", ".")
                    )  # Преобразуем курс в число
                    rates[currency_name] = {
                        "buy_rate": buy_rate_value,
                        "rate_per_ruble": 1
                        / buy_rate_value,  # Рассчитываем курс валюты за 1 рубль
                    }
                except ValueError:
                    print(
                        f"Ошибка преобразования курса для {currency_name}: {buy_rate}"
                    )

        # Отбираем только нужные валюты, учитывая оба названия
        usd_rate_per_ruble = rates.get("Usd", rates.get("Доллар", {})).get(
            "rate_per_ruble", None
        )
        eur_rate_per_ruble = rates.get("Eur", rates.get("Евро", {})).get(
            "rate_per_ruble", None
        )
        cny_rate_per_ruble = rates.get("Cny", rates.get("Юань", {})).get(
            "rate_per_ruble", None
        )

        return usd_rate_per_ruble, eur_rate_per_ruble, cny_rate_per_ruble

    except Exception as e:
        print(f"Ошибка: {e}")
        return None, None, None


def get_thai_currency_rates():
    # URL API
    api_url = "https://www.superrichthailand.com/web/api/v1/rates"

    # Учетные данные для Basic Auth
    username = "superrichTh"  # Логин
    password = "hThcirrepus"  # Пароль

    # Отправляем GET-запрос с Basic Auth
    response = requests.get(api_url, auth=HTTPBasicAuth(username, password))

    # Проверяем, успешен ли запрос
    if response.status_code == 200:
        data = response.json()  # Преобразуем ответ в JSON

        # Извлекаем курсы валют
        exchange_rates = data["data"]["exchangeRate"]

        # Список валют, которые мы хотим извлечь
        target_currencies = ["USD", "EUR", "CNY", "RUB"]

        # Словарь для хранения максимальных курсов
        max_currency_rates = {
            currency: {"Buying Rate": 0} for currency in target_currencies
        }

        # Извлекаем нужные данные
        for currency in exchange_rates:
            currency_unit = currency["cUnit"]
            rates = currency["rate"]

            if currency_unit in target_currencies:
                for rate in rates:
                    # Проверяем, является ли текущий курс покупки максимальным
                    if (
                        rate["cBuying"]
                        > max_currency_rates[currency_unit]["Buying Rate"]
                    ):
                        max_currency_rates[currency_unit]["Buying Rate"] = rate[
                            "cBuying"
                        ]

        # Создаем переменные для каждой валюты
        usd_rate = (
            max_currency_rates["USD"]["Buying Rate"]
            if "USD" in max_currency_rates
            else None
        )
        eur_rate = (
            max_currency_rates["EUR"]["Buying Rate"]
            if "EUR" in max_currency_rates
            else None
        )
        cny_rate = (
            max_currency_rates["CNY"]["Buying Rate"]
            if "CNY" in max_currency_rates
            else None
        )
        rub_rate = (
            max_currency_rates["RUB"]["Buying Rate"]
            if "RUB" in max_currency_rates
            else None
        )

        return usd_rate, eur_rate, cny_rate, rub_rate
    else:
        print(f"Ошибка при запросе: {response.status_code}")
        return None, None, None, None


def convert_currency(
    amount_rub,
    rub_to_usd,
    rub_to_eur,
    rub_to_cny,
    thb_from_usd,
    thb_from_eur,
    thb_from_cny,
    thb_from_rub,
):
    # Конвертация
    thb_from_rub = amount_rub * thb_from_rub  # курс рубль к бат
    thb_from_usd = (amount_rub * rub_to_usd) * thb_from_usd  # курс доллар к бат
    thb_from_eur = (amount_rub * rub_to_eur) * thb_from_eur  # курс евро к бат
    thb_from_cny = (amount_rub * rub_to_cny) * thb_from_cny  # курс юань к бат

    return thb_from_rub, thb_from_usd, thb_from_eur, thb_from_cny


# Обработчик нажатия на кнопки выбора валют
@dp.callback_query_handler(lambda c: c.data in ['rub_usd_bat', 'rub_eur_bat', 'rub_cny_bat', 'rub_bat', 'all_variants'])
async def process_currency_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    selected_option = callback_query.data

    # Получаем сумму в рублях из состояния пользователя
    user_data = await state.get_data()
    amount_rub = user_data['amount']

    # Получаем сумму в рублях из состояния пользователя
    user_data = await state.get_data()
    amount_rub = user_data['amount']

    # Вычисляем курсы валют
    thb_from_rub, thb_from_usd, thb_from_eur, thb_from_cny = convert_currency(
        amount_rub,
        rub_to_usd,
        rub_to_eur,
        rub_to_cny,
        thb_from_usd,
        thb_from_eur,
        thb_from_cny,
        thb_from_rub,
    )

    # Формируем сообщение в зависимости от выбранного варианта
    if selected_option == 'rub_usd_bat':
        message = f"Курс Рубль-Доллар-Бат: {thb_from_usd} THB"
    elif selected_option == 'rub_eur_bat':
        message = f"Курс Рубль-Евро-Бат: {thb_from_eur} THB"
    elif selected_option == 'rub_cny_bat':
        message = f"Курс Рубль-Юань-Бат: {thb_from_cny} THB"
    elif selected_option == 'rub_bat':
        message = f"Курс Рубль-Бат: {thb_from_rub} THB"
    elif selected_option == 'all_variants':
        message = (f"Курс Рубль-Доллар-Бат: {thb_from_usd} THB\n"
                   f"Курс Рубль-Евро-Бат: {thb_from_eur} THB\n"
                   f"Курс Рубль-Юань-Бат: {thb_from_cny} THB\n"
                   f"Курс Рубль-Бат: {thb_from_rub} THB")

    await bot.send_message(callback_query.from_user.id, message)

@dp.message_handler()
async def convert(message: types.Message):
    try:
        amount_rub = float(message.text.replace(",", "."))
        url = "https://ru.myfin.by/currency/usd/moskva"
        usd_rate_per_ruble, eur_rate_per_ruble, cny_rate_per_ruble = get_currency_rates(url)
        thb_usd, thb_eur, thb_cny, thb_rub = get_thai_currency_rates()
        thb_from_rub, thb_from_usd, thb_from_eur, thb_from_cny = convert_currency(amount_rub, usd_rate_per_ruble, eur_rate_per_ruble, cny_rate_per_ruble, thb_usd, thb_eur, thb_cny, thb_rub)
        await message.reply(f"Рубль-бат: {thb_from_rub:.2f} THB\nРубль-доллар-бат: {thb_from_usd:.2f} THB\nРубль-евро-бат: {thb_from_eur:.2f} THB\nРубль-юань-бат: {thb_from_cny:.2f} THB")
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число.")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
