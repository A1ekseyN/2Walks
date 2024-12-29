import json
import requests
from datetime import datetime, timedelta

# Константы для работы с OAuth2
CLIENT_ID = "476016277833-1onej6om5goqq3vmq7srtun8sm4oig22.apps.googleusercontent.com"
CLIENT_SECRET = "ВАШ_CLIENT_SECRET"
REFRESH_TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_SCOPE = "https://www.googleapis.com/auth/fitness.activity.read"
REDIRECT_URI = "http://localhost"

def save_token_to_file(token_data, file_path="token.json"):
    """Сохраняет токен в файл."""
    try:
        with open(file_path, 'w') as file:
            json.dump(token_data, file, indent=4)
        print("Токен успешно сохранен в файл.")
    except Exception as e:
        print(f"Ошибка при сохранении токена: {e}")

def load_token_from_file(file_path="token.json"):
    """Загружает токен из файла."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
        return None
    except json.JSONDecodeError:
        print("Ошибка чтения JSON из файла.")
        return None

def create_token():
    """
    Проводит начальную аутентификацию и возвращает токен.
    Включает перенаправление пользователя для авторизации.
    """
    print("Перейдите по следующей ссылке для получения кода авторизации:")
    print(f"https://accounts.google.com/o/oauth2/auth?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={AUTH_SCOPE}&response_type=code")

    # Получаем код авторизации от пользователя
    auth_code = input("Введите код авторизации: ")

    # Отправляем запрос для получения токена
    data = {
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(REFRESH_TOKEN_URL, data=data)
    if response.status_code == 200:
        token_data = response.json()
        # Сохраняем токен в файл
        save_token_to_file(token_data)
        return token_data
    else:
        print("Ошибка получения токена:", response.json())
        return None

def refresh_token(file_path="token.json"):
    """Обновляет истекший токен, используя refresh_token."""
    token_data = load_token_from_file(file_path)
    if not token_data or "refresh_token" not in token_data:
        print("Refresh токен отсутствует. Необходимо пройти авторизацию.")
        return None

    refresh_token = token_data["refresh_token"]
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(REFRESH_TOKEN_URL, data=data)
    if response.status_code == 200:
        new_token_data = response.json()
        # Обновляем refresh_token и сохраняем токен
        token_data.update(new_token_data)
        save_token_to_file(token_data)
        return new_token_data["access_token"]
    else:
        print("Ошибка обновления токена:", response.json())
        return None


create_token()
