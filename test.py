from characteristics import char_characteristic, skill_training_table

#skill_training_table = {
#    1: {
#        'steps': 1000,
#        'time': 0,
#        'energy': 5,
#        'money': 10,
#    },
#}

print(skill_training_table)
print(skill_training_table[1]['steps'])
print(skill_training_table[char_characteristic['stamina']+1]['energy'])
print(skill_training_table[char_characteristic['stamina'] + 1]['time'])

