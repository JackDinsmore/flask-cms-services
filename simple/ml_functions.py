from keras.models import load_model
import tensorflow as tf
import keras.backend as K

from tensorflow.python.util import deprecation
deprecation._PRINT_DEPRECATION_WARNINGS = False

import os, time

global predict_permitted
predict_permitted = True

def predict(data):
    global predict_permitted
    while not predict_permitted:
        pass # Wait until server is clear
    predict_permitted = False
    model = load_model("mnist-cnn.h5")
    with tf.device('/gpu:0'):
        predictions = model.predict(data).astype(float)
    K.clear_session()
    ret = []
    for line in predictions:
        ret.append(list(line))
    predict_permitted = True
    return predictions, ret
