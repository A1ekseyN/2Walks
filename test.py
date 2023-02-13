from characteristics import char_characteristic


print(len(char_characteristic["inventory"]))
print(range(0, len(char_characteristic["inventory"])))

for i in range(1, len(char_characteristic["inventory"]) + 1):
    print(i)

print(max(range(1, len(char_characteristic['inventory']) + 1)))

print(f'Кол-во items: {len(char_characteristic["inventory"])}')

print(char_characteristic["inventory"][0])