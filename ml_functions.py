from keras.models import load_model

from tensorflow.python.util import deprecation
deprecation._PRINT_DEPRECATION_WARNINGS = False

import os

def predict(data):
    model = load_model("mnist-cnn.h5")
    predictions = model.predict(data).astype(float)
    ret = []
    for line in predictions:
        ret.append(list(line))
    return predictions, ret
