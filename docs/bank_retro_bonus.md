# Bank Retro-Bonus: дизайнерское решение

Документ описывает механику банка в 2Walks — а именно тот факт, что прокачка скиллов `banking_interest_rate` и `loan_interest_reduction` **ретроактивно** пересчитывает накопленные проценты по новой ставке. Это **намеренный design choice**, а не баг. Документ нужен чтобы:

1. Игрок понимал «как тут зарабатывать максимум денег» — это часть стратегии.
2. Будущий maintainer (или будущий я) не «починил» эту механику случайно, приняв за ошибку.

Status: **активно с версии 0.2.4z (20.05.2026)**. Tasks: 4.49.1.2 (deposit) + 4.49.2.3 (loan).

---

## 1. Суть механики

### Депозит

```
T=0      Открыл депозит 1,000$ при skill banking_interest_rate = 1 (rate = 1% годовых)
T=30d    Прокачал banking_interest_rate с 1 до 10 (rate = 10% годовых)
T=30d+ε  Сделал top-up на 1$ (или withdraw на 1$ — любая mutation)
         ↓
         accrue_deposit() капитализирует проценты:
           elapsed   = 30 дней с last_interest_ts (T=0)
           rate      = 10% (current, после прокачки)
           interest  = 1000 × 0.10 × 30/365 ≈ 8.22$
         ↓
         Депозит вырос с 1,000$ до ~1,008.22$
```

**Ключевое:** проценты считаются по **текущей** (после прокачки) ставке за **весь** прошедший период с момента открытия. Это retro-bonus — игрок «зарабатывает заранее» когда повышает скилл.

### Кредит

```
T=0      Взял кредит 1,000$ при skill loan_interest_reduction = 0 (rate = 100% годовых)
T=30d    Прокачал loan_interest_reduction с 0 до 50 (rate = 50% годовых)
T=30d+ε  Сделал repay (любую сумму)
         ↓
         accrue_loan() капитализирует проценты:
           elapsed   = 30 дней с last_interest_ts
           rate      = 50% (current, после прокачки)
           interest  = 1000 × 0.50 × 30/365 ≈ 41.10$
         ↓
         Долг = 1,041.10$ (вместо 1,082.19$ если бы accrue прошёл по 100%)
         Игрок «сэкономил» ~41$ за счёт прокачки
```

Симметричная механика — retro-DISCOUNT для кредита.

---

## 2. Почему это design, а не баг

### Аргумент 1: симметрия с work / earnings_boost (4.23)

Та же механика уже работает в **зарплате** с версии 0.2.4a (06.05.2026, task 4.23 «Earnings Boost»). См. `work.py:215-227`:

```python
if state.work.end <= now:
    # 4.23 — earnings_boost: state.work.salary базовая, итог считается
    # через apply_earnings_boost (recompute — учитывает текущий уровень
    # skill, даже если он был прокачан во время смены).
    base_salary = state.work.salary
    effective_salary = apply_earnings_boost(base_salary, state)
    earned = effective_salary * state.work.hours
    state.money += earned
```

Сценарий с зарплатой полностью аналогичен:

```
T=0      Стартовал смену Watchman 8 часов с earnings_boost = 0 (base 110.75 $/час)
T=ε..    Параллельно тренируешь earnings_boost
T=8h     Финализация → apply_earnings_boost читает СВЕЖИЙ уровень скилла
         → бонус применяется ко всем 8 часам (а не только к тем что прошли после прокачки)
```

Если в банке закрыли retro-bonus, а в работе оставили — это **inconsistent**. С 0.2.4z обе системы используют одинаковый pattern: **recompute с текущим уровнем скилла на момент финализации/mutation**, а не **lock-on-start**.

### Аргумент 2: стимул прокачивать скиллы

Без retro-bonus оптимальная стратегия игрока:

1. Прокачать `banking_interest_rate` ДО депозита (иначе бесплатные дни).
2. Прокачать `loan_interest_reduction` ДО кредита (иначе платишь по 100%).

Это создаёт **порог входа** для банковской системы: чтобы начать использовать депозиты, надо сначала вбухать ресурсы в прокачку. Игрок без скилла → банк бесполезен.

С retro-bonus оптимальная стратегия:

1. **Открой депозит как можно раньше** — даже при skill=1 (rate 1%) деньги работают на тебя.
2. **Прокачивай скилл параллельно** — каждый уровень applies к накопленному времени.
3. **Затягивай withdraw / repay** до удобного момента — больше времени = больше retro-эффект.

Это создаёт **incentive loop**: открыл депозит → видишь рост → хочется быстрее прокачать скилл → больше retro-bonus → ещё хочется. Стимул для прокачки `banking_interest_rate` (который иначе вообще необязателен — игра жилаема без банка).

То же для кредитов: если игрок берёт кредит «по ситуации» (нужны шаги срочно для прокачки Stamina lvl 19+), он платит 100%. Но если он параллельно качает `loan_interest_reduction`, retro-discount даёт реальную экономию.

### Аргумент 3: согласуется с pattern «recompute, не snapshot»

В 2Walks почти все производные значения **recompute** на лету, а не **snapshot** на момент события:

| Helper | Recompute? | Где |
|---|---|---|
| `bonus.compute_energy_max(state)` | ✅ | каждый раз когда нужен energy_max |
| `bonus.apply_money_saving(cost, state)` | ✅ | на момент покупки/тренировки |
| `bonus.apply_earnings_boost(salary, state)` | ✅ | на момент финализации смены |
| `bonus.apply_trader(price, state)` | ✅ | на момент продажи |
| `bonus.apply_energy_optimization_*(energy, state)` | ✅ | на момент старта активности |
| `bonus.energy_regen_interval(60, state)` | ✅ | каждый тик регена |
| `equipment_*_bonus(state)` | ✅ | каждый раз когда нужно |
| `current_deposit_rate_pct(state)` | ✅ | на момент accrue |
| `current_loan_rate_pct(state)` | ✅ | на момент accrue |

Lock-on-start был бы исключением, ради «защиты от exploit». 0.2.4z приводит банк к общему pattern'у.

### Аргумент 4: cozy / step-counter game, не competitive PvP

2Walks — single-player cozy RPG где основной challenge — **реальные шаги в реальной жизни**. «Exploit» здесь не разрушает баланс между игроками (их нет) и не ломает интенсивность gameplay (один игрок может выжать дополнительные ~50$ в день — на фоне доходов уровня 800-900$ за полную смену это marginal). Стимул прокачивать скиллы важнее «правильности» формулы процентов.

---

## 3. Numerical examples — насколько большой retro-bonus?

### Депозит

Параметры: депозит 10,000$, rate растёт с 1% до 10% после 30 дней.

| Сценарий | Final amount (через 60 дней) |
|---|---|
| **С retro-bonus (текущее):** rate=10% применяется ко всем 60 дням на следующий accrue | ≈ 10,164.38 $ |
| **Без retro-bonus (старая логика):** 30 дней по 1% + 30 дней по 10% | ≈ 10,090.41 $ |
| **Разница (retro-выигрыш):** | ≈ 73.97 $ |

Зависит от: размера депозита (линейно), разницы между старой и новой ставкой, продолжительности «отстаивания» под низкой ставкой до прокачки.

### Кредит

Параметры: кредит 1,000$, rate снижается со 100% до 50% после 30 дней (skill `loan_interest_reduction` 0 → 50).

| Сценарий | Долг (через 60 дней) |
|---|---|
| **С retro-discount (текущее):** rate=50% применяется ко всем 60 дням | ≈ 1,082.19 $ |
| **Без retro-discount (старая логика):** 30 дней по 100% + 30 дней по 50% | ≈ 1,123.29 $ |
| **Разница (retro-выигрыш):** | ≈ 41.10 $ |

Кредит = «обратный депозит»: retro-bonus тут означает «меньше платишь», а не «больше получаешь».

### Real-world upper bound

Чтобы получить значимый retro-bonus, нужны три условия:
1. Большая сумма (депозит / долг).
2. Большой разрыв ставок (низкая на момент открытия, высокая после прокачки).
3. Длительное «отстаивание» между открытием и прокачкой.

В практике игрока:
- Прокачка `banking_interest_rate` с 0 до 10 занимает ~64 часа реального training-time + ресурсы.
- За эти 64 часа депозит в 10k $ при rate 0% (default) не растёт вообще. С прокачкой → 10k × 10% × 2.6 дня / 365 ≈ 7.12 $ retro.
- Получается ~7 $ за 64 часа реального времени — это **очень маленький** реальный выигрыш в сравнении с зарплатой 800+ $/смену.

То есть **exploit существует механически**, но **не доминирует gameplay**. Он работает как «приятный бонус для тех кто прокачивает банк» — а это и есть цель.

---

## 4. Implementation: где именно сделано

### Файл: `gym.py:skill_training_check_done()`

**До 0.2.4z** (закрытый exploit, tasks 4.49.1.1 + 4.49.2.1):

```python
skill_name = state.training.skill_name
# capitalize-on-skill-up — для banking_interest_rate
# и loan_interest_reduction сначала начисляем проценты по СТАРОЙ ставке за
# прошедший период, потом инкрементим скилл. Иначе новая ставка применилась
# бы задним числом (exploit). Lazy import — избегаем циклов.
if skill_name == 'banking_interest_rate':
    from bank import accrue_deposit
    accrue_deposit(state)
elif skill_name == 'loan_interest_reduction':
    from bank import accrue_loan
    accrue_loan(state)
old_level = getattr(state.gym, skill_name)
new_level = old_level + 1
setattr(state.gym, skill_name, new_level)
```

**После 0.2.4z** (открытый exploit, tasks 4.49.1.2 + 4.49.2.3):

```python
skill_name = state.training.skill_name
# 4.49.1.2 / 4.49.2.3 (0.2.4z): retro-bonus exploit ОТКРЫТ намеренно —
# симметрично earnings_boost (4.23). accrue срабатывает только на mutation
# (top-up / withdraw / take_loan / repay), новая ставка применяется
# ретроактивно к накопленному времени. Stimulus для прокачки скиллов:
# «открыл депозит → прокачал → собрал с retro-процентами» / «взял кредит
# → прокачал reduction → отдал меньше».
old_level = getattr(state.gym, skill_name)
new_level = old_level + 1
setattr(state.gym, skill_name, new_level)
```

10-строчный if-блок удалён. `accrue_deposit` / `accrue_loan` остались pure helpers в `bank.py` без изменений — они вызываются только на mutation (`_deposit_*`, `_withdraw_*`, `_take_loan`, `_repay_*`).

### Файл: `bank.py` — без изменений

Все pure helpers остались как есть:
- `accrue_deposit(state)` / `accrue_loan(state)` — капитализируют по `current_*_rate_pct(state)` (текущая ставка)
- `_deposit(state, amount)` / `_withdraw(state, amount)` / `_take_loan(state, amount)` / `_repay_loan(state, amount)` — каждая вызывает `accrue_*` ПЕРЕД мутацией тела (capitalize-on-change).

`current_deposit_rate_pct(state)` и `current_loan_rate_pct(state)` всегда возвращают **текущий** уровень скилла — потому что они pure read функции без снимка состояния.

### Файл: `tests/test_bank.py`

2 теста инвертированы:
- `test_skill_up_no_accrue_retro_bonus_applies` (deposit) — проверяет что после skill-up `last_interest_ts` НЕ сдвигается, и следующий ручной `accrue_deposit` применяет новую ставку к **всему** периоду.
- `test_skill_up_no_accrue_for_loan_retro_discount` (loan) — то же для кредита (retro-DISCOUNT).

2 «нерегрессионных» теста оставлены как есть:
- `test_skill_up_hook_does_not_fire_for_other_skills` — прокачка stamina не трогает депозит.
- `test_skill_up_hook_does_not_affect_loan_for_other_skills` — то же для кредита.

(Эти 2 теста стали избыточными после 0.2.4z — теперь **ни один** скилл не дёргает accrue — но они служат regression защитой если кто-то снова добавит hook.)

---

## 5. Для maintainer'а: не «чините» это

Если кто-то в будущем посмотрит на код и подумает «погоди, тут же exploit — игрок может ретроактивно получить проценты по новой ставке»:

1. **Это не ошибка.** Прочти этот документ.
2. **Это согласовано с pattern earnings_boost.** Закрытие exploit'а сделает банк inconsistent с зарплатой.
3. **Это попросил игрок** (Oleksii, 20.05.2026 — см. discussion в conversation, фиксация в `changelog.txt` 0.2.4z).
4. **Это документировано в CLAUDE.md** (bank.py section).
5. **Это задокументировано в TASKS.md** (4.49.1.2 + 4.49.2.3, оба done).

Если по каким-то причинам появится необходимость *закрыть* exploit (баланс ушёл слишком в плюс игрока, или появилось новое design соображение) — это будет **новая задача** (например 4.49.1.3 или 4.49.2.4), с явным обоснованием и обновлением этого документа. Не надо просто восстанавливать старый hook молча.

---

## 6. Связанные документы

- `CLAUDE.md` — секция `bank.py` (since 0.2.2 / task 4.49) описывает механику кратко.
- `changelog.txt` — entry для версии 0.2.4z с обоснованием изменения.
- `TASKS.md` — секции 4.49.1.1 / 4.49.1.2 (deposit) и 4.49.2.1 / 4.49.2.3 (loan) — история изменения hook'а.
- `bank.py` — pure helpers (`accrue_deposit`, `accrue_loan`, mutation functions). Без специальной retro-bonus логики — она «эмерджентная» из факта что `current_*_rate_pct(state)` всегда reads текущий уровень.
- `gym.py:skill_training_check_done` — место где раньше был hook (теперь удалён).
- `tests/test_bank.py` — `test_skill_up_no_accrue_retro_bonus_applies` / `test_skill_up_no_accrue_for_loan_retro_discount` — fixate retro-bonus поведение тестами.

---

## 7. История изменений

| Дата | Версия | Что |
|---|---|---|
| 06.05.2026 | 0.2.2 | task 4.49.1.1 — добавлен hook `accrue_deposit` перед `banking_interest_rate++` (закрыт exploit) |
| 06.05.2026 | 0.2.2 | task 4.49.2.1 — добавлен hook `accrue_loan` перед `loan_interest_reduction++` (закрыт exploit) |
| 20.05.2026 | 0.2.4z | tasks 4.49.1.2 + 4.49.2.3 — hooks удалены (exploit **открыт намеренно**) |
