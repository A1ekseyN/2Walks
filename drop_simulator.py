# Tasks:
# - Добавить рандом для качества шмотки (20 - 100 %)
# - Luck влияет на качество шмотки randint(0, luck)

from random import randint
import time


start_time = time.time()

drop_percent_gl = 80
drop_percent_item_a = 75
drop_percent_item_b = 60
drop_percent_item_c = 45

luck = 8
cnt = 0
cnt_a = 0
cnt_b = 0
cnt_c = 0
cnt_cycle = 0

a_stamina_items = 0
a_energy_max_items = 0
a_speed_skill_items = 0
a_luck_items = 0
a_unluck = 0
a_ring = 0
a_necklace = 0
a_jewelery_unluck = 0

b_stamina_items = 0
b_energy_max_items = 0
b_speed_skill_items = 0
b_luck_items = 0
b_unluck = 0
b_ring = 0
b_necklace = 0
b_jewelery_unluck = 0

c_stamina_items = 0
c_energy_max_items = 0
c_speed_skill_items = 0
c_luck_items = 0
c_unluck = 0
c_ring = 0
c_necklace = 0
c_jewelery_unluck = 0

attempt = 1000000

# Вычисление drop происходит по формуле уменьшения drop_percent_a


def show_progress_bar(x):
    if x == 0.1:
        print(f'- 10 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.2:
        print(f'- 20 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.3:
        print(f'- 30 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.4:
        print(f'- 40 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.5:
        print(f'- 50 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.6:
        print(f'- 60 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.7:
        print(f'- 70 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.8:
        print(f'- 80 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')
    elif x == 0.9:
        print(f'- 90 % - {timer_hrs_min_sec(time.time() - start_time)} -- {drop_percent_temp()} %.')


def timer_hrs_min_sec(x):
    minutes = x // 60
    sec = x % 60
    return f'{round(minutes)} min {round(sec)} sec.'


def drop_percent_temp():
    drop_percent_tempp = (cnt / cnt_cycle) * 100
    return round(drop_percent_tempp, 2)


def random_one_item():
    global cnt_cycle
    global cnt

    for t in range(0, attempt):
        cnt_cycle += 1                      # Переменная для вычисления drop % в ходе вычислений.
        x = t / attempt                     # Вычисление Progress Bar %.
        show_progress_bar(x)                # Отображение в % хода выполнения симуляции.

        i = randint(1, 100 - luck)
        if i <= drop_percent_gl:            # Определение выпал предмет да или нет.
            a = randint(1, 100 - luck)
            if a <= drop_percent_item_a:    # Определение или выпал предмет с учетом собственного drop шанса.
                cnt += 1

    drop_percent = (cnt / attempt) * 100  # Глобальный drop %, показывается в конце вычислений.

    print('\nDrop Item C-Grade.')
    print(f'Dropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round(drop_percent, 2)} %)')
    print(f"Скрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")


def random_two_items():
    global cnt_cycle, cnt, cnt_a, cnt_b

    for t in range(0, attempt):
        cnt_cycle += 1                              # Переменная для вычисления drop % в ходе вычислений.
        x = t / attempt                             # Вычисление Progress Bar %.
        show_progress_bar(x)                        # Отображение в % хода выполнения симуляции.

        i = randint(1, 100 - luck)
        if i <= drop_percent_gl:                    # Определение выпал предмет да или нет.
            a = randint(1, 100 - luck)
            b = randint(1, 100 - luck)
            if a > b and a <= drop_percent_item_a:  # Определение или выпал предмет A с учетом собственного drop шанса.
                cnt += 1
                cnt_a += 1
            if b > a and b <= drop_percent_item_b:  # Определение или выпал предмет B с учетом собственного drop шанса.
                cnt += 1
                cnt_b += 1

    print(f'\nLuck: {luck}.')
    print(f'Dropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round((cnt / attempt) * 100, 2)} %)')
    print(f'Item Drop Chance:\n- Item A: {round((cnt_a / attempt) * 100, 2)} %.'
          f'\n- Item B: {round((cnt_b / attempt) * 100, 2)} %.')
    print(f"Скрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")

# Два предмета: Stat -> Item
def random_two_items_characteristics_stat_item():
    global cnt_cycle, cnt, cnt_a, cnt_b
    global a_stamina_items, a_energy_max_items, a_speed_skill_items, a_luck_items, a_unluck
    global b_stamina_items, b_energy_max_items, b_speed_skill_items, b_luck_items, b_unluck
    global a_ring, a_necklace, b_ring, b_necklace, a_jewelery_unluck, b_jewelery_unluck

    for t in range(0, attempt):
        cnt_cycle += 1                              # Переменная для вычисления drop % в ходе вычислений.
        x = t / attempt                             # Вычисление Progress Bar %.
        show_progress_bar(x)                        # Отображение в % хода выполнения симуляции.

        i = randint(1, 100 - luck)
        if i <= drop_percent_gl:                    # Определение выпал предмет да или нет.
            a = randint(1, 100 - luck)
            b = randint(1, 100 - luck)

            # A- Grade
            if a > b and a <= drop_percent_item_a:  # Определение или выпал предмет A с учетом собственного drop шанса.
                cnt += 1
                cnt_a += 1

                a_stamina = randint(1, 100 + luck)
                a_energy_max = randint(1, 100 + luck)
                a_speed_skill = randint(1, 100 + luck)
                a_luck = randint(1, 100 + luck)

                if a_stamina > a_energy_max and a_stamina > a_speed_skill and a_stamina > a_luck:
                    a_stamina_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        a_ring += 1
                    elif ring < necklace:
                        a_necklace += 1
                    else:
                        cnt_a -= 1
                        a_jewelery_unluck += 1
                elif a_energy_max > a_stamina and a_energy_max > a_speed_skill and a_energy_max > a_luck:
                    a_energy_max_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        a_ring += 1
                    elif ring < necklace:
                        a_necklace += 1
                    else:
                        cnt_a -= 1
                        a_jewelery_unluck += 1
                elif a_speed_skill > a_stamina and a_speed_skill > a_energy_max and a_speed_skill > a_luck:
                    a_speed_skill_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        a_ring += 1
                    elif ring < necklace:
                        a_necklace += 1
                    else:
                        cnt_a -= 1
                        a_jewelery_unluck += 1
                elif a_luck > a_stamina and a_luck > a_energy_max and a_luck > a_speed_skill:
                    a_luck_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        a_ring += 1
                    elif ring < necklace:
                        a_necklace += 1
                    else:
                        cnt_a -= 1
                        a_jewelery_unluck += 1
                else:
                    cnt_a -= 1
                    a_unluck += 1

            # B-Grade
            if b > a and b <= drop_percent_item_b:  # Определение или выпал предмет B с учетом собственного drop шанса.
                cnt += 1
                cnt_b += 1

                b_stamina = randint(1, 100 + luck)
                b_energy_max = randint(1, 100 + luck)
                b_speed_skill = randint(1, 100 + luck)
                b_luck = randint(1, 100 + luck)

                if b_stamina > b_energy_max and b_stamina > b_speed_skill and b_stamina > b_luck:
                    b_stamina_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        b_ring += 1
                    elif ring < necklace:
                        b_necklace += 1
                    else:
                        cnt_b -= 1
                        b_jewelery_unluck += 1
                elif b_energy_max > b_stamina and b_energy_max > b_speed_skill and b_energy_max > b_luck:
                    b_energy_max_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        b_ring += 1
                    elif ring < necklace:
                        b_necklace += 1
                    else:
                        cnt_b -= 1
                        b_jewelery_unluck += 1
                elif b_speed_skill > b_stamina and b_speed_skill > b_energy_max and b_speed_skill > b_luck:
                    b_speed_skill_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        b_ring += 1
                    elif ring < necklace:
                        b_necklace += 1
                    else:
                        cnt_b -= 1
                        b_jewelery_unluck += 1
                elif b_luck > b_stamina and b_luck > b_energy_max and b_luck > b_speed_skill:
                    b_luck_items += 1
                    ring = randint(1, 100 + luck)
                    necklace = randint(1, 100 + luck)
                    if ring > necklace:
                        b_ring += 1
                    elif ring < necklace:
                        b_necklace += 1
                    else:
                        cnt_b -= 1
                        b_jewelery_unluck += 1
                else:
                    cnt_b -= 1
                    b_unluck += 1

    print(f'\nLuck: {luck}.')
    print(f'Dropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round((cnt / attempt) * 100, 2)} %)')
    print(f'\nItem Drop Chance:'
          f'\n-- Item A: {round((cnt_a / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((a_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((a_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((a_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((a_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((a_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((a_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((a_necklace / attempt) * 100)} %; '
          f'Unluck: {round((a_jewelery_unluck / attempt) * 100, 2)} %.'
          
          f'\n-- Item B: {round((cnt_b / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((b_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((b_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((b_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((b_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((b_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((b_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((b_necklace / attempt) * 100)} %; '
          f'Unluck: {round((b_jewelery_unluck / attempt) * 100, 2)} %.')

    print(f"\nСкрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")


# Два предмета: Item -> Stat
def random_two_items_characteristics_item_stat():
    global cnt_cycle, cnt, cnt_a, cnt_b
    global a_stamina_items, a_energy_max_items, a_speed_skill_items, a_luck_items, a_unluck
    global b_stamina_items, b_energy_max_items, b_speed_skill_items, b_luck_items, b_unluck
    global a_ring, a_necklace, b_ring, b_necklace, a_jewelery_unluck, b_jewelery_unluck

    for t in range(0, attempt):
        cnt_cycle += 1  # Переменная для вычисления drop % в ходе вычислений.
        x = t / attempt  # Вычисление Progress Bar %.
        show_progress_bar(x)  # Отображение в % хода выполнения симуляции.

        i = randint(1, 100 - luck)
        if i <= drop_percent_gl:  # Определение выпал предмет да или нет.
            a = randint(1, 100 - luck)
            b = randint(1, 100 - luck)

            # A- Grade
            if a > b and a <= drop_percent_item_a:  # Определение или выпал предмет A с учетом собственного drop шанса.
                cnt += 1
                cnt_a += 1

                ring = randint(1, 100 + luck)
                necklace = randint(1, 100 + luck)

                if ring > necklace:
                    a_ring += 1

                    a_stamina = randint(1, 100 + luck)
                    a_energy_max = randint(1, 100 + luck)
                    a_speed_skill = randint(1, 100 + luck)
                    a_luck = randint(1, 100 + luck)

                    if a_stamina > a_energy_max and a_stamina > a_speed_skill and a_stamina > a_luck:
                        a_stamina_items += 1
                    elif a_energy_max > a_stamina and a_energy_max > a_speed_skill and a_energy_max > a_luck:
                        a_energy_max_items += 1
                    elif a_speed_skill > a_stamina and a_speed_skill > a_energy_max and a_speed_skill > a_luck:
                        a_speed_skill_items += 1
                    elif a_luck > a_stamina and a_luck > a_energy_max and a_luck > a_speed_skill:
                        a_luck_items += 1
                    else:
                        cnt_a -= 1
                        a_unluck += 1

                elif ring < necklace:
                    a_necklace += 1

                    a_stamina = randint(1, 100 + luck)
                    a_energy_max = randint(1, 100 + luck)
                    a_speed_skill = randint(1, 100 + luck)
                    a_luck = randint(1, 100 + luck)

                    if a_stamina > a_energy_max and a_stamina > a_speed_skill and a_stamina > a_luck:
                        a_stamina_items += 1
                    elif a_energy_max > a_stamina and a_energy_max > a_speed_skill and a_energy_max > a_luck:
                        a_energy_max_items += 1
                    elif a_speed_skill > a_stamina and a_speed_skill > a_energy_max and a_speed_skill > a_luck:
                        a_speed_skill_items += 1
                    elif a_luck > a_stamina and a_luck > a_energy_max and a_luck > a_speed_skill:
                        a_luck_items += 1
                    else:
                        cnt_a -= 1
                        a_unluck += 1
                else:
                    cnt_a -= 1
                    a_jewelery_unluck += 1

            # B-Grade
            if b > a and b <= drop_percent_item_b:  # Определение или выпал предмет B с учетом собственного drop шанса.
                cnt += 1
                cnt_b += 1

                ring = randint(1, 100 + luck)
                necklace = randint(1, 100 + luck)

                if ring > necklace:
                    b_ring += 1

                    b_stamina = randint(1, 100 + luck)
                    b_energy_max = randint(1, 100 + luck)
                    b_speed_skill = randint(1, 100 + luck)
                    b_luck = randint(1, 100 + luck)

                    if b_stamina > b_energy_max and b_stamina > b_speed_skill and b_stamina > b_luck:
                        b_stamina_items += 1
                    elif b_energy_max > b_stamina and b_energy_max > b_speed_skill and b_energy_max > b_luck:
                        b_energy_max_items += 1
                    elif b_speed_skill > b_stamina and b_speed_skill > b_energy_max and b_speed_skill > b_luck:
                        b_speed_skill_items += 1
                    elif b_luck > b_stamina and b_luck > b_energy_max and b_luck > b_speed_skill:
                        b_luck_items += 1
                    else:
                        cnt_b -= 1
                        b_unluck += 1

                elif ring < necklace:
                    b_necklace += 1

                    b_stamina = randint(1, 100 + luck)
                    b_energy_max = randint(1, 100 + luck)
                    b_speed_skill = randint(1, 100 + luck)
                    b_luck = randint(1, 100 + luck)

                    if b_stamina > b_energy_max and b_stamina > b_speed_skill and b_stamina > b_luck:
                        b_stamina_items += 1
                    elif b_energy_max > b_stamina and b_energy_max > b_speed_skill and b_energy_max > b_luck:
                        b_energy_max_items += 1
                    elif b_speed_skill > b_stamina and b_speed_skill > b_energy_max and b_speed_skill > b_luck:
                        b_speed_skill_items += 1
                    elif b_luck > b_stamina and b_luck > b_energy_max and b_luck > b_speed_skill:
                        b_luck_items += 1
                    else:
                        cnt_b -= 1
                        b_unluck += 1
                else:
                    cnt_a -= 1
                    a_jewelery_unluck += 1


    print(f'\nLuck: {luck}.')
    print(f'Dropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round((cnt / attempt) * 100, 2)} %)')
    print(f'\nItem Drop Chance:'
          f'\n-- Item A: {round((cnt_a / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((a_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((a_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((a_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((a_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((a_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((a_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((a_necklace / attempt) * 100)} %; '
          f'Unluck: {round((a_jewelery_unluck / attempt) * 100, 2)} %.'

          f'\n-- Item B: {round((cnt_b / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((b_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((b_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((b_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((b_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((b_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((b_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((b_necklace / attempt) * 100)} %; '
          f'Unluck: {round((b_jewelery_unluck / attempt) * 100, 2)} %.')

    print(f"\nСкрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")


def random_thee_items_characteristics_item_stat():
    global cnt_cycle, cnt, cnt_a, cnt_b, cnt_c
    global a_stamina_items, a_energy_max_items, a_speed_skill_items, a_luck_items, a_unluck
    global b_stamina_items, b_energy_max_items, b_speed_skill_items, b_luck_items, b_unluck
    global c_stamina_items, c_energy_max_items, c_speed_skill_items, c_luck_items, c_unluck
    global a_ring, a_necklace, b_ring, b_necklace, a_jewelery_unluck, b_jewelery_unluck
    global c_ring, c_necklace, c_jewelery_unluck, c_jewelery_unluck

    for t in range(0, attempt):
        cnt_cycle += 1  # Переменная для вычисления drop % в ходе вычислений.
        x = t / attempt  # Вычисление Progress Bar %.
        show_progress_bar(x)  # Отображение в % хода выполнения симуляции.

        i = randint(1, 100 - luck)
        if i <= drop_percent_gl:  # Определение выпал предмет да или нет.
            a = randint(1, 100 - luck)
            b = randint(1, 100 - luck)
            c = randint(1, 100 - luck)

            # A-Grade
            if a > b and a <= drop_percent_item_a or a > c and a <= drop_percent_item_a:  # Определение или выпал предмет A с учетом собственного drop шанса.
                cnt += 1
                cnt_a += 1

                ring = randint(1, 100 + luck)
                necklace = randint(1, 100 + luck)

                if ring > necklace:
                    a_ring += 1

                    a_stamina = randint(1, 100 + luck)
                    a_energy_max = randint(1, 100 + luck)
                    a_speed_skill = randint(1, 100 + luck)
                    a_luck = randint(1, 100 + luck)

                    if a_stamina > a_energy_max and a_stamina > a_speed_skill and a_stamina > a_luck:
                        a_stamina_items += 1
                    elif a_energy_max > a_stamina and a_energy_max > a_speed_skill and a_energy_max > a_luck:
                        a_energy_max_items += 1
                    elif a_speed_skill > a_stamina and a_speed_skill > a_energy_max and a_speed_skill > a_luck:
                        a_speed_skill_items += 1
                    elif a_luck > a_stamina and a_luck > a_energy_max and a_luck > a_speed_skill:
                        a_luck_items += 1
                    else:
                        cnt_a -= 1
                        a_unluck += 1

                elif ring < necklace:
                    a_necklace += 1

                    a_stamina = randint(1, 100 + luck)
                    a_energy_max = randint(1, 100 + luck)
                    a_speed_skill = randint(1, 100 + luck)
                    a_luck = randint(1, 100 + luck)

                    if a_stamina > a_energy_max and a_stamina > a_speed_skill and a_stamina > a_luck:
                        a_stamina_items += 1
                    elif a_energy_max > a_stamina and a_energy_max > a_speed_skill and a_energy_max > a_luck:
                        a_energy_max_items += 1
                    elif a_speed_skill > a_stamina and a_speed_skill > a_energy_max and a_speed_skill > a_luck:
                        a_speed_skill_items += 1
                    elif a_luck > a_stamina and a_luck > a_energy_max and a_luck > a_speed_skill:
                        a_luck_items += 1
                    else:
                        cnt_a -= 1
                        a_unluck += 1
                else:
                    cnt_a -= 1
                    a_jewelery_unluck += 1

            # B-Grade
            if b > a and b <= drop_percent_item_b or b > c and b <= drop_percent_item_b:  # Определение или выпал предмет B с учетом собственного drop шанса.
                cnt += 1
                cnt_b += 1

                ring = randint(1, 100 + luck)
                necklace = randint(1, 100 + luck)

                if ring > necklace:
                    b_ring += 1

                    b_stamina = randint(1, 100 + luck)
                    b_energy_max = randint(1, 100 + luck)
                    b_speed_skill = randint(1, 100 + luck)
                    b_luck = randint(1, 100 + luck)

                    if b_stamina > b_energy_max and b_stamina > b_speed_skill and b_stamina > b_luck:
                        b_stamina_items += 1
                    elif b_energy_max > b_stamina and b_energy_max > b_speed_skill and b_energy_max > b_luck:
                        b_energy_max_items += 1
                    elif b_speed_skill > b_stamina and b_speed_skill > b_energy_max and b_speed_skill > b_luck:
                        b_speed_skill_items += 1
                    elif b_luck > b_stamina and b_luck > b_energy_max and b_luck > b_speed_skill:
                        b_luck_items += 1
                    else:
                        cnt_b -= 1
                        b_unluck += 1

                elif ring < necklace:
                    b_necklace += 1

                    b_stamina = randint(1, 100 + luck)
                    b_energy_max = randint(1, 100 + luck)
                    b_speed_skill = randint(1, 100 + luck)
                    b_luck = randint(1, 100 + luck)

                    if b_stamina > b_energy_max and b_stamina > b_speed_skill and b_stamina > b_luck:
                        b_stamina_items += 1
                    elif b_energy_max > b_stamina and b_energy_max > b_speed_skill and b_energy_max > b_luck:
                        b_energy_max_items += 1
                    elif b_speed_skill > b_stamina and b_speed_skill > b_energy_max and b_speed_skill > b_luck:
                        b_speed_skill_items += 1
                    elif b_luck > b_stamina and b_luck > b_energy_max and b_luck > b_speed_skill:
                        b_luck_items += 1
                    else:
                        cnt_b -= 1
                        b_unluck += 1
                else:
                    cnt_a -= 1
                    a_jewelery_unluck += 1

           # C-Grade
            if c > a and c <= drop_percent_item_c or c > b and c <= drop_percent_item_c:  # Определение или выпал предмет B с учетом собственного drop шанса.
                cnt += 1
                cnt_c += 1

                ring = randint(1, 100 + luck)
                necklace = randint(1, 100 + luck)

                if ring > necklace:
                    c_ring += 1

                    c_stamina = randint(1, 100 + luck)
                    c_energy_max = randint(1, 100 + luck)
                    c_speed_skill = randint(1, 100 + luck)
                    c_luck = randint(1, 100 + luck)

                    if c_stamina > c_energy_max and c_stamina > c_speed_skill and c_stamina > c_luck:
                        c_stamina_items += 1
                    elif c_energy_max > c_stamina and c_energy_max > c_speed_skill and c_energy_max > c_luck:
                        c_energy_max_items += 1
                    elif c_speed_skill > c_stamina and c_speed_skill > c_energy_max and c_speed_skill > c_luck:
                        c_speed_skill_items += 1
                    elif c_luck > c_stamina and c_luck > c_energy_max and c_luck > c_speed_skill:
                        c_luck_items += 1
                    else:
                        cnt_c -= 1
                        c_unluck += 1

                elif ring < necklace:
                    c_necklace += 1

                    c_stamina = randint(1, 100 + luck)
                    c_energy_max = randint(1, 100 + luck)
                    c_speed_skill = randint(1, 100 + luck)
                    c_luck = randint(1, 100 + luck)

                    if c_stamina > c_energy_max and c_stamina > c_speed_skill and c_stamina > c_luck:
                        c_stamina_items += 1
                    elif c_energy_max > c_stamina and c_energy_max > c_speed_skill and c_energy_max > c_luck:
                        c_energy_max_items += 1
                    elif c_speed_skill > c_stamina and c_speed_skill > c_energy_max and c_speed_skill > c_luck:
                        c_speed_skill_items += 1
                    elif c_luck > c_stamina and c_luck > c_energy_max and c_luck > c_speed_skill:
                        c_luck_items += 1
                else:
                    cnt_c -= 1
                    c_unluck += 1


    print(f'\nLuck: {luck}.')
    print(f'Dropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round((cnt / attempt) * 100, 2)} %)')
    print(f'\nItem Drop Chance:'
          f'\n--- Item A: {round((cnt_a / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((a_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((a_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((a_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((a_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((a_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((a_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((a_necklace / attempt) * 100)} %; '
          f'Unluck: {round((a_jewelery_unluck / attempt) * 100, 4)} %.'

          f'\n--- Item B: {round((cnt_b / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((b_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((b_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((b_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((b_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((b_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((b_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((b_necklace / attempt) * 100)} %; '
          f'Unluck: {round((b_jewelery_unluck / attempt) * 100, 4)} %.'

          f'\n--- Item C: {round((cnt_c / attempt) * 100, 2)} %.'
          f' --- (Stamina: {round((c_stamina_items / attempt) * 100, 2)} %; '
          f'Energy_max: {round((c_energy_max_items / attempt) * 100, 2)} %; '
          f'Speed: {round((c_speed_skill_items / attempt) * 100, 2)} %; '
          f'Luck: {round((c_luck_items / attempt) * 100, 2)} %; '
          f'Unluck: {round((c_unluck / attempt) * 100, 2)} %).'
          f'\n- Кольца: {round((c_ring / attempt) * 100, 2)} %; '
          f'Ожерелье: {round((c_necklace / attempt) * 100)} %; '
          f'Unluck: {round((c_jewelery_unluck / attempt) * 100, 4)} %.')

    print(f"\nСкрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")


#random_one_item()                                    # Вычисление рандома для 1 Item A
#random_two_items()                                   # Вычисление рандома для 2 Items A + B
#random_two_items_characteristics_stat_item()         # Вычисление рандома для 2 Items A + B с учетом характеристик
#random_two_items_characteristics_item_stat()
random_thee_items_characteristics_item_stat()

drop_percent = (cnt / attempt) * 100                  # Глобальный drop %, показывается в конце вычислений.


#print(f'\nDropped out of {attempt:,.0f} attemptsCounter: {cnt:,.0f}. ({round(drop_percent, 2)} %)')
#print(f'Item Drop Chance:\n- Item A: {round((cnt_a / attempt) * 100, 2)} %.'
#      f'\n- Item B: {round((cnt_b / attempt) * 100, 2)} %.')
#print(f"Скрипт выполнен за: {timer_hrs_min_sec(time.time() - start_time)} секунды.")

### Global chance - 70 %.
# 1 Item with chance - 75 %. (Drop Chance: 52.5 % +- 0.01)

### Global chance - 75 %
# 1 Item with chance - 75 %. (Drop Chance: 56.25 %)

### Global chance - 80 %
# 1 Item with chance - 75 %. (Drop Chance: 60 %)

# 2 (A+B) Luck: 0 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 36.36 % (A: 22.2 %, B: 14.16 %)
# 2 (A+B) Luck: 1 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 37.xx % (A: 22.87 %, B: 14.6 %)
# 2 (A+B) Luck: 5 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 42.xx % (A: 25.89 %, B: 16.52 %)
# 2 (A+B) Luck: 10 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 49.88 % (A: 30.45 %, B: 19.42 %)
# 2 (A+B) Luck: 15 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 59.21 % (A: 36.16 %, B: 23.05 %)
# 2 (A+B) Luck: 20 -- Items with chance A - 75 %, B - 60 %. (Drop Chance: 71.02 % (A: 43.36 %, B: 27.66 %)

# 2 (A+B) Luck: 0 with Items x4 --- Items with chance A - 75 %, B - 60 %.
# (Drop Chance: 36.36 % (A: 21.54 %, B: 13.74 %, unluck A: 0.44 % + B: 0.28 %) (A Item chr: 5.44 %; B Item chr: 3.47 %) (Ring: 6.87 %; Necklace: 7 %; UnLuck: 0.14 %) (Time: 12:19)
# 2 (A+B) Luck: 1 with Items x4 --- Items with chance A - 75 %, B - 60 %.
# (Drop Chance: 37.47 % (A: 22.21 %, B: 14.16 %, unluck A: 0.45 % + B: 0.29 %) (A Item chr: 5.6 %; B Item chr: 3.58 %) (Ring A: 11 %; Ring B: 7 %; UnLuck: 0.14 %) (Time: 11:02)
# 2 (A+B) Luck: 20 with Items x4 --- Items with chance A - 75 %, B - 60 %.
# (Drop Chance: 71.01 % (A: 42.29 %, B: 26.96 %, unluck A: 0.72 % + B: 0.46 %) (A Item chr: 10.66 %; B Item chr: 6.8 %) (Ring A: 21.1 %; Ring B: 13.48 %; UnLuck: 0.23 %) (Time: 15:41)

# Item -> Characteristic algoritm:
# 2 (A+B) Luck: 0 with Items x4 --- Items with chance A - 75 %, B - 60 %.
# (Drop Chance: 36.36 % (A: 21.4 %, B: 13.88 %, unluck A: 0.44 % + B: 0.28 %) (A Item chr: 5.38 %; B Item chr: 3.43 %) (Ring A: 11 %; Ring B: 7 %; UnLuck: 0 %) (Time: 12:47)
# 2 (A+B) Luck: 20 with Items x4 --- Items with chance A - 75 %, B - 60 %.
# (Drop Chance: 71.02 % (A: 42.06 %, B: 27.21 %, unluck A: 0.72 % + B: 0.45 %) (A Item chr: 10.57 %; B Item chr: 6.75 %) (Ring A: 21.5 %; Ring B: 13.71 %; UnLuck: 0 %) (Time: 16:26)

# 3 (A+B+C) Luck: 0 with Items x4 --- Items with chance A - 75 %, B - 60 %, C - 45 %.
# (Drop Chance: 69.58 % (A: 32.16 %, B: 22.26 %, C: 13.23% unluck A: 0.66 % + B: 0.45 % + C: 0.27 %)
# (A Item chr: 8.1 %; B Item chr: 5.51; C Item chr: 3.27 %) (Ring A: 16.52 %; Ring B: 11 %; Ring C: 6.68 % UnLuck: 0 %) (Time: 17:24)

