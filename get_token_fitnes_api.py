from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json

# Scopes для Fitness API
SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read']
TOKEN_FILE = 'token.json'

def save_token(creds):
    """Сохраняет токены в файл."""
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

def load_token():
    """Загружает токены из файла."""
    try:
        with open(TOKEN_FILE, 'r') as token_file:
            token_data = json.load(token_file)
            return Credentials.from_authorized_user_info(token_data, SCOPES)
    except FileNotFoundError:
        return None

def get_access_token():
    creds = load_token()
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('fitness_api_credential.json', SCOPES)
            creds = flow.run_local_server(port=0)
        save_token(creds)  # Сохраняем токены
    return creds.token

token = get_access_token()
print(f"Access Token: {token}")
