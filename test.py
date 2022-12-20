from datetime import datetime

now_date = datetime.now().date()
now_time = datetime.now().time()
#print(now_date)
#print(now_time)

#now_time = datetime.now().time()


# Тест записи и чтения файлов
save_game_file = open('save.txt', 'r')
save = save_game_file.read()
print(save)

save_game_file = open('save.txt', 'w')
save_game_file.write(f"{str(now_date)}")
#save_game_file.write(f"{str(now_time)}")
save_game_file.close()
