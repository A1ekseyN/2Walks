from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json


SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'fitness_api_credential.json'


def save_token(creds):
    """
    Сохраняет токены в файл.
    :param creds: Объект Credentials, содержащий токены.
    """
    try:
        with open(TOKEN_FILE, 'w') as token_file:
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
            }
            json.dump(token_data, token_file)
            print(f"Токен сохранен в {TOKEN_FILE}.")
    except Exception as e:
        print(f"Ошибка при сохранении токена: {e}")

def load_token():
    """
    Загружает токены из файла.
    :return: Объект Credentials или None, если токен не найден или недействителен.
    """
    try:
        with open(TOKEN_FILE, 'r') as token_file:
            token_data = json.load(token_file)
            return Credentials.from_authorized_user_info(token_data, SCOPES)
    except FileNotFoundError:
        print(f"Файл {TOKEN_FILE} не найден. Пожалуйста, выполните авторизацию.")
        return None
    except json.JSONDecodeError:
        print(f"Ошибка чтения {TOKEN_FILE}.")
        return None


def get_access_token():
    """
    Получает access token. Если токен недействителен, выполняется обновление или повторная авторизация.
    :return: Строка access token.
    """
    creds = load_token()

    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                print("Token has expired. Update token...")
                creds.refresh(Request())
            else:
                print("New authorization")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            save_token(creds)
        except Exception as e:
            print(f"Ошибка при получении токена: {e}")
            return None

    return creds.token


if __name__ == "__main__":
    # Получаем токен авторизации для Fitness API
    token = get_access_token()

    if token:
        print(f"Access Token: {token}")
    else:
        print("Не удалось получить токен.")
