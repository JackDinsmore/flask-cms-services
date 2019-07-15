from keras.models import load_model

def predict(data):
    model = load_model("./mnist-cnn.h5")
    print("Model loaded")
    predictions = model.predict(data)
    return predictions
