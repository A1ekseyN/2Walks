from colorama import Fore, Style


def time(x):
    # Функция для преобразования времени в часы и минуты.
    if x <= 60:
        return f'{Fore.LIGHTBLUE_EX}{x}{Style.RESET_ALL} мин.'
    elif x > 60:
        hours = int(x // 60)
        min = int(x % 60)
        return f'{Fore.LIGHTBLUE_EX}{hours}{Style.RESET_ALL} часов {Fore.LIGHTBLUE_EX}{min}{Style.RESET_ALL} мин.'
