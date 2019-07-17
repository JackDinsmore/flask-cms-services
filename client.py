import requests, time
import numpy as np

while input() == '':
    image = open('image.bmp', 'rb')
    b = image.read()[54:]# remove header
    image.close()
    assert(len(b)==28*28*3)
    data = np.ndarray((1, 28, 28, 1))
    for y in range(28):
        for x in range(28):
            i = 3*(28*y+x)
            data[0][27-y][x][0] = 1 - (int(b[i])+int(b[i+1])+int(b[i+2])) / 3 / 255
                # Read from bottom up for some reason
    data = data.tostring().hex()

    id = requests.post("http://127.0.0.1:5000", 
        data={'name': 'jd1', 'data':str(data), "num_samples":1, 'hang':True}).text
    print(id)
