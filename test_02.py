# Тестовый файл для записи игровых характеристик и данны в файл.

import pickle

data = {
    'a': [1, 2.0, 3, 4 + 6j],
    'b': ("character string", "byte string"),
    'c': {None, True, False}
}

# сохранение в файл
with open('test_data.txt', 'wb') as f:
    pickle.dump(data, f)

# чтение из файла
with open('test_data.txt', 'rb') as f:
    data_new = pickle.load(f)

print(data_new['a'][0])