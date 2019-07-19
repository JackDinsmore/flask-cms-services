'''
This file is part of a simple tutorial for how to use the MNIST server that
Jack Dinsmore developed in the summer of 2019.

PURPOSE: read data from a bitmap image of a handwritten number and send it
to a server to predict what number it is.

DEPENDENCIES:
- image.bmp: the image to predict on. Should be black and white, where the
background is white and the number is black. Should be 28 x 28 pixels
    Note: this tutorial assumes that the header of the image is 54 bytes and
    removes it. If reading the image data fails, it may be because the header
    is a different size. Check to make sure the file format is .bmp. Issues
    may also be the fault of the image editor's saving algorithm; this
    tutorial has been tested in MS Paint.
'''

import requests, time
import numpy as np

# Input the name of the server; it changes
# every time I take down and redeploy the server
ip=input("IP of the server: ")

# Number of images that we push to the server to predict on.
NUM_SAMPLES = 1

# The program runs in an infinite loop so that you can
# change the image between posts if you want.
while input() == '':
    # Load data from the image
    image = open('image.bmp', 'rb')
    b = image.read()[54:]# Remove header
    image.close()
    assert(len(b)==28*28*3)# Make sure the image has no transparency and is 28x28
    data = np.ndarray((NUM_SAMPLES, 28, 28, 1))
    for y in range(28):
        for x in range(28):
            # Add the color data pixel by pixel to the np array.
            # For some reason, MNIST wants to receive images with inverted
            #   colors and with the vertical axis inverted. So this is implemeneted.
            i = 3*(28*y+x)
            data[0][27-y][x][0] = 1 - (int(b[i])+int(b[i+1])+int(b[i+2])) / 3 / 255
    # Convert the data to a string so that it can be transferred to the server
    data = data.tostring().hex()

    # Give the data to the server
    answer = requests.post("http://"+ip+":5000", 
        data={'name': 'jd1', 'data':str(data), "num_samples":NUM_SAMPLES}).text

    # Check if an error has occurred on the server in processing your image.
    # If you wish to know what error occurred, navigate to the ip address of
    # the server in a web browser and click the link "error" next to your
    # job's ID. (The ID was assigned by the server; you may not know it, but
    # it's probably the most recent).
    if "Error" in answer or 'error' in answer:
        print(answer)
        continue
    try:
        # Convert the answer back to a numpy array
        answer = np.frombuffer(bytes.fromhex(answer)).reshape(NUM_SAMPLES, 10)
    except:
        print(answer)
        continue

    # The output is a length-10 array of probabilities, so that the value of the
    # ith item is the probability that the number in image.bmp was i. Finding
    # the index of the largest value in the list will give the most likely
    # answer.
    answer_list=list(answer[0])
    print("Prediction: answer_list.index(max(answer_list)))")
