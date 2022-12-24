import time
from datetime import datetime, timedelta
from work import work_check_done

a = datetime.now().timestamp()
print(a)
#b = datetime.now().timetuple()
#c = datetime.now().timestamp()
#d = datetime.fromtimestamp(c)

#print(d)
#print(d + timedelta(hours=2))
#print(c)
#time.sleep(1)
#print(datetime.now().timestamp())
#print(datetime.now().timestamp() - 10)


work_check_done()


