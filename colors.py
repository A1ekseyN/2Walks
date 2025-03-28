from colorama import Fore, Style


def steps_color(x):
    # Шаги окрашиваем в светло-синий цвет
    x = f'{Fore.LIGHTCYAN_EX}{x:,.0f}{Style.RESET_ALL}'
    return x


def energy_color(x):
    # Функция для окрашивания энергии в зеленом цвете.
    x = f'{Fore.GREEN}{x}{Style.RESET_ALL}'
    return x
