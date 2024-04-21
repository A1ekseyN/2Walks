import requests
from bs4 import BeautifulSoup


def get_ebay_info(url):
    # Отправляем GET-запрос к указанной странице eBay
    response = requests.get(url)

    # Проверяем успешность запроса
    if response.status_code == 200:
        # Используем BeautifulSoup для парсинга HTML-кода страницы
        soup = BeautifulSoup(response.text, 'html.parser')

        # Находим элемент, содержащий информацию о цене, bids и времени окончания аукциона
        bid_info = soup.find('div', class_='vim x-bid-price')

        if bid_info:
            # Получаем информацию о цене
            price = bid_info.find('span', class_='ux-textspans').text.strip()

            # Получаем количество bids
            bids = bid_info.find('span', class_='ux-textspans--PSEUDOLINK').text.strip()

            # Получаем время окончания аукциона
            time_left = bid_info.find('span', class_='ux-timer__text').text.strip()

            return {'price': price, 'bids': bids, 'time_left': time_left}
        else:
            return {'error': 'Не удалось найти информацию о ставке на странице'}
    else:
        return {'error': 'Не удалось выполнить запрос к странице eBay'}


# Пример использования
url = 'https://www.ebay.com/itm/375274186271?itmmeta=01HQKHRAYF82CRFCYCHX2CTSGE&hash=item576015a61f%3Ag%3AyQsAAOSwq1hl2Uvw&itmprp=enc%3AAQAIAAAA4PNkdOsEUQPZa8sDjJw78xxYJyIxjhKudmvoOVckTAJ2YCTsBcQ7%2BPyXn0eJ9yWfZV3vNBVJf00eL0n0C%2F5BIZdDb5RSfe%2BjX7tQ8gF%2Fej9u20GGAVQkVGHm5oSfixJVG8zyKRDe%2BgpU%2B%2B9HG74cElXYD45kFPIZksHJGOhdFtpLUwJEq%2BYr%2BSrm9LlFnIJbklmlHsrnhlOtQXZALUEirEiHS4JEHoWFuoermjW2hld5bfjqFQ3PK6xdB9QXDd968wupnftT1Jcg%2Bi9BO%2BWehXvELSrnvU%2BBjbg2nwMn8Ax5%7Ctkp%3ABk9SR6Kv4fG8Yw&LH_Auction=1'
result = get_ebay_info(url)
if 'error' in result:
    print('Ошибка:', result['error'])
else:
    print('Цена:', result['price'])
    print('Ставки:', result['bids'])
    print('Время до окончания аукциона:', result['time_left'])


def place_bid(url, max_bid):
    # URL для отправки запроса
    bid_url = f"{url.split('?')[0]}/placebid/{url.split('/')[-1].split('?')[0]}"
    print(f"bid_url: {bid_url}")

    # Параметры для POST-запроса
    params = {
        'maxbid': max_bid,
        # Другие необходимые параметры, если есть
    }

    # Отправка POST-запроса
    response = requests.post(bid_url, data=params)
    print(f"Responce: {response}")

    # Проверка успешности запроса
    if response.status_code == 200:
        return {'success': True, 'message': 'Ставка успешно поднята'}
    else:
        return {'error': 'Не удалось поднять ставку'}


# Пример использования
url = 'https://www.ebay.com/itm/375274186271?itmmeta=01HQKHRAYF82CRFCYCHX2CTSGE&hash=item576015a61f%3Ag%3AyQsAAOSwq1hl2Uvw&itmprp=enc%3AAQAIAAAA4PNkdOsEUQPZa8sDjJw78xxYJyIxjhKudmvoOVckTAJ2YCTsBcQ7%2BPyXn0eJ9yWfZV3vNBVJf00eL0n0C%2F5BIZdDb5RSfe%2BjX7tQ8gF%2Fej9u20GGAVQkVGHm5oSfixJVG8zyKRDe%2BgpU%2B%2B9HG74cElXYD45kFPIZksHJGOhdFtpLUwJEq%2BYr%2BSrm9LlFnIJbklmlHsrnhlOtQXZALUEirEiHS4JEHoWFuoermjW2hld5bfjqFQ3PK6xdB9QXDd968wupnftT1Jcg%2Bi9BO%2BWehXvELSrnvU%2BBjbg2nwMn8Ax5%7Ctkp%3ABk9SR6Kv4fG8Yw&LH_Auction=1'
max_bid = '12.00'  # Указываем сумму до которой нужно поднять ставку
result = place_bid(url, max_bid)
if 'error' in result:
    print('Ошибка:', result['error'])
    print(f"Error: {result}")
elif 'success' in result:
    print(result['message'])
