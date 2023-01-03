from datetime import datetime, timedelta
from characteristics import char_characteristic, skill_training_table


a = datetime.now().timestamp()


print(datetime.fromtimestamp(datetime.now().timestamp()))
#print(datetime.fromtimestamp(datetime.now().timestamp()) + datetime.fromtimestamp(d))

print(datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic['speed_skill'] + 1]['time'])))
b = (datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic['speed_skill'] + 1]['time'])) - datetime.fromtimestamp(datetime.now().timestamp()))
print(b)
print(type(b))
#print(datetime.fromtimestamp(datetime.timetuple(b)))
c = timedelta(minutes=(skill_training_table[char_characteristic['speed_skill'] + 1]['time']))
print(f'c = {c}')

print('######################')
print(datetime.now().timestamp())
print(skill_training_table[char_characteristic['speed_skill'] + 1]['time'])
print(f"test = {datetime.now().timestamp() + (skill_training_table[char_characteristic['speed_skill'] + 1]['time'])}")
print(datetime.now().timestamp() + (skill_training_table[char_characteristic['speed_skill'] + 1]['time']) - datetime.now().timestamp())
test_01 = datetime.now().timestamp() + (skill_training_table[char_characteristic['speed_skill'] + 1]['time']) - datetime.now().timestamp()
test_02 = test_01 - ((test_01 / 100) * 2)
test_03 = test_02 * 60
test_04 = datetime.now().timestamp() + test_03
print(test_04)
#print(datetime.fromtimestamp(test_04) - datetime.now().timestamp())

print('#####')

skill_training_time = round(skill_training_table[char_characteristic["speed_skill"] + 1]["time"]) * 60
print(f'skill_training_time: {skill_training_time}')
skill_training_time_with_bonus = skill_training_time - ((skill_training_time / 100) * 1)
print(f'speed_bonus: {skill_training_time_with_bonus}')
chr = datetime.fromtimestamp(datetime.now().timestamp() + skill_training_time_with_bonus)

print(chr)
print(datetime.fromtimestamp(datetime.now().timestamp()) + timedelta(minutes=(skill_training_table[char_characteristic["speed_skill"] + 1]['time'])))

print(datetime.fromtimestamp(datetime.now().timestamp()) + (char_characteristic['working_hours'] * 60))

#q = 100
#print(q)
#print(q - ((q / 100) * 1))
