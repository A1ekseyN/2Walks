from characteristics import char_characteristic, skill_training_table
from datetime import datetime, timedelta

char_characteristic['skill_training_name'] = 'stamina'

class Skill_Training():
    # Класс инициализации работы

    def __init__(self, training, name, timestamp, time_end, time_stamp_now):
        # Инициализация атрибутов
        self.training = training
        self.name = name
        self.timestamp = timestamp
        self.time_end = time_end
        self.timestamp_now = time_stamp_now
        print('\n--- Skill Training.---')
        print(f'Train: {self.training}')
        print(f'Skill name: {self.name}')
        print(f'Time_stamp: {self.timestamp}')
        print(f'Time_end: {self.time_end}')
        print(f'Time_stamp_now: {self.timestamp_now}')

    def start_skill_training(self):
        # Начало обучения навыка
        print(f'\n--- Start skill training. ---')
        char_characteristic['skill_training'] = True
        char_characteristic['skill_training_name'] = self.name
        char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
        char_characteristic['skill_training_time_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic[self.name] + 1]['time']))
        char_characteristic['steps_today_used'] += (char_characteristic[self.name] + 1) * 1000
        char_characteristic['energy'] -= (char_characteristic[self.name] + 1) * 5
        char_characteristic['money'] -= (char_characteristic[self.name] + 1) * 10
        print(f'\n🏋️ {self.name.title()} - Начато улучшение навыка.')
        print(f'🕑 Окончание тренировки навыка через: {char_characteristic["skill_training_time_end"] - datetime.fromtimestamp(datetime.now().timestamp())}.')
        return char_characteristic


skill = Skill_Training(char_characteristic['skill_training'], char_characteristic['skill_training_name'],
                       char_characteristic['skill_training_timestamp'], char_characteristic['skill_training_time_end'], datetime.now().timestamp())
print(skill.start_skill_training())

print(char_characteristic['skill_training'])
print(char_characteristic['skill_training_time_end'])

#char_characteristic['skill_training'] = True
#char_characteristic['skill_training_name'] = 'stamina'
#char_characteristic['skill_training_timestamp'] = datetime.now().timestamp()
#char_characteristic['skill_training_time_end'] = datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic['stamina'] + 1]['time']))
#char_characteristic['steps_today_used'] += (char_characteristic['stamina'] + 1) * 1000
#char_characteristic['energy'] -= (char_characteristic['stamina'] + 1) * 5
#char_characteristic['money'] -= (char_characteristic['stamina'] + 1) * 10

print()


