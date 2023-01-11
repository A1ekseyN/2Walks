from datetime import datetime, timedelta

a = datetime.now().timestamp()
b = datetime.now().timestamp()
c = datetime.fromtimestamp(datetime.now().timestamp()) - datetime.fromtimestamp(datetime.now().timestamp())

print(datetime.now().fromtimestamp(a).strftime("%d:%I:%M:%S"))

print(datetime.fromtimestamp(datetime.now().timestamp()) - datetime.fromtimestamp(datetime.now().timestamp()))

print(c)

#date.strftime("%A %d %B %Y")
