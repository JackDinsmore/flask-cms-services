import requests, time

while input() == '':
    id = requests.post("http://127.0.0.1:5000", data={'name': 'jd1', 'data':None}).text
    #r = requests.post("http://127.0.0.1:5000", data={'name': 'jd1', 'hang':'true', 'data':None})
    print("Sent")
    while True:
        r = requests.post("http://127.0.0.1:5000", data={'id': id})
        print(r.text)
        time.sleep(1)
