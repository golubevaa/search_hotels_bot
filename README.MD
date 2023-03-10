# TelegramBot для поиска отелей

Бот найдёт лучшие отели согласно вашему запросу - следуйте инструкциям и выбирайте :) \
В данный момент поиск по России недоступен.
## Подготовка к эксплуатации

### 1. Установка

Создайте виртуальное окружение и активируйте его. \
В виртуальном окружении выполните:

```
pip install -r requirements.txt
```

### 2. Настройка

В файле bot_settings в параметре TOKEN укажите токен бота, полученный от BotFather. \
В параметре RAPIDAPI_TOKEN укажите токен для доступа к hotels api. 

Содержание bot_settings должно быть следующим:

```
import telebot

TOKEN = 'Ваш токен от BotFather'
RAPIDAPI_TOKEN = "Ваш токен для запросов к rapidapi"

headers = {
    "X-RapidAPI-Key": RAPIDAPI_TOKEN,
    "X-RapidAPI-Host": "hotels4.p.rapidapi.com"
}

bot = telebot.TeleBot(f"{TOKEN}")
```

### 3. Запуск

В активированном вирутальном окружении выполните:

```
python main.py
```

## Эксплуатация

### Список команд бота:

* [/start](#start)
* [/hello_world](#hello_world)
* [/help](#help)
* [/lowprice](#lowprice)
* [/highprice](#highprice)
* [/bestdeal](#bestdeal)
* [/history](#history)

### Start

Присылает ознакомительное сообщение.

### Hello_world

Присылает "Hello, world!"

### Help

Присылает список всех доступных команд с описанием.

### Lowprice

Запускает сценарий поиска самых дешевых отелей в указанной локации.

### Highprice

Запускает сценарий поиска самых дорогих отелей в указанной локации.

### Bestdeal

Запускает сценарий поиска отелей в указанном ценовом диапазоне, не дальше указанного расстояния от центра в км.

### History

Выводит информацию с результатами прошлых поисков пользователя. Если у пользователя нет истории - выведет сообщение о том, что истории пока нет.

## Описание поисковых сценариев

Команды lowprice, highprice, bestdeal начинают общий сценарий опроса пользователя для подбора отелей.
На каждом шаге бот присылает сообщения, на которые либо требуется ответить текстовым сообщением, либо выбрать вариант на встроенной клавиатуре.

Шаги:

| шаг                                                       | способ ответа         | команда               | Ограничения                                                                                               |
|-----------------------------------------------------------|-----------------------|-----------------------|-----------------------------------------------------------------------------------------------------------|
| Ввести город для поиска                                   | текстовое сообщение   | все поисковые команды | -                                                                                                         |
| Выбрать город из предложенных                             | встроенная клавиатура | все поисковые команды | -                                                                                                         |
| Ввести количество отелей для поиска                       | встроенная клавиатура | все поисковые команды | 10 отелей                                                                                                 |
| Ввести дату заезда                                        | встроенная клавиатура | все поисковые команды | не дальше 1 года от текущей даты                                                                          |
| Ввести дату выезда                                        | встроенная клавиатура | все поисковые команды | не дальше даты заезда + 1 год                                                                             |
| Ввести кол-во взрослых в 1 номере                         | встроенная клавиатура | все поисковые команды | не больше 14                                                                                              |
| Наличие детей в номере                                    | встроенная клавиатура | все поисковые команды | -                                                                                                         |
| Ввод возраста каждого <br/>из детей при их наличии        | встроенная клавиатура | все поисковые команды | только при положительном ответе<br/>на предыдущем шаге.<br/> В комнате может быть не больше <br/> 6 детей |
| Ввод минимальной и <br/>максимальной стоимости за ночь, $ | текстовое сообщение   | bestdeal              | два положительных числа через пробел<br/>(Можно с дробной частью)                                         |
| Ввод максимально допустимого<br/>расстояния до центра, км | текстовое сообщение   | bestdeal              | положительное число (Можно с дробной частью)                                                              |
| Наличие фотографий в ответе                               | встроенная клавиатура | все поисковые команды | -                                                                                                         |
| Ввести требуемое<br/>кол-во фотографий в ответе           | встроенная клавиатура | все поисковые команды | 10 фотографий                                                                                             |

Реализована возможность добавления дополнительных номеров и изменения всех данных, введенных с помощью встроенных клавиатур.

### Общие ограничения

1. Дата заезда не может быть меньше даты выезда.
2. Кол-во людей в одном бронировании не может быть больше 20.

В случае нарушения этих правил переход к поиску не произойдет - бот попросит исправить эти моменты.

### Результаты:

В случае успешного поиска отелей по требуемым параметрам, бот выведет информацию о каждом отеле в отдельном сообщении.
Сообщение содержит:
* Название отеля
* Рейтинг
* Адрес 
* Расстояние до центра
* Стоимость за ночь, $
* Сумма, $
* Ссылка на отель!
* Фотографии (если они требовались)

Пример результата:

![alt text](https://user-images.githubusercontent.com/113348198/216898858-0b399b4d-feb9-4730-b415-8287f586296f.PNG)

## Описание сценария работы команды history

Для сохранения результатов поиска пользователей используется база данных SQLite. 
При запуске скрипт создает БД и таблицу history, если она еще не создана. 
Запись в базу производится после отправки пользователю всех сообщений, которые были сформированы в рамках его запроса.
Один пользовательский запрос, для которого были найдены и отправлены результаты, формирует одну строку в таблице.

При выполнении команды /history в БД производится поиск всех записей, ассоциированных с telegram_id пользователя.
Пользователю будет оправлено кол-во сообщений, равное кол-ву его успешных запросов.
Каждое сообщение содержит:

* Локацию
* Дату и время запроса
* Команду запроса
* список отелей (их названия и ссылки на них)
