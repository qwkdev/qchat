import requests as rq
import time

URL = "http://127.0.0.1:5000"

# user = input('Username: ')
# auth = '' if not user else input('Auth: ')
# channel = input('Enter channel: ')

user = "pyclient"
channel = "main"


def epoch() -> int:
    return int(time.time())


last = 0
while True:
    resp = rq.post(f"{URL}/get/{channel}?after={last}", json={"user": user})

    if not resp.ok:
        print(resp.status_code, resp.content)
        print("Error getting json")
        continue

    data = resp.json()
    if not data.get("success"):
        if data.get("error"):
            print("Error:", data.get("error"))
            continue

        print("Misc error")
        continue

    for msg in data.get("chat", []):
        print(msg)
    last = msg[0]

    time.sleep(2)
