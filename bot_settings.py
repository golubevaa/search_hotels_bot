import telebot


TOKEN = ''
RAPIDAPI_TOKEN = ""

headers = {
    "X-RapidAPI-Key": RAPIDAPI_TOKEN,
    "X-RapidAPI-Host": "hotels4.p.rapidapi.com"
}


bot = telebot.TeleBot(f"{TOKEN}")