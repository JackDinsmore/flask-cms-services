import os, time, sys

from flask import Flask, request, render_template
import flask_socketio as io
import multiprocessing as mp
from . import ml_functions as ml
import numpy as np

global clients, pkg_data, max_id, first_connection, kernel
clients = []
pkg_data = None# temporary
kernel = None# temporary
max_id=0
first_connection = True

app = Flask(__name__, instance_relative_config=True)
socketio = io.SocketIO()

def run(pkg_data):
    while True:
        now = time.time()
        for i in range(len(pkg_data)):
            if pkg_data[i]['timeout'] != None and now > pkg_data[i]['timeout']:
                pkg_data[i]['status'] = 'timed out'

        for i in range(len(pkg_data)):
            if pkg_data[i]['status'] == 'waiting':
                pkg_data[i]['status'] = 'running'
                try:
                    result = ml.predict(np.random.rand(1, 28, 28, 1))#pkg_data[i]['data'])
                    pkg_data[i]['status'] = 'finished'
                    print("Result!:", result)
                    pkg_data[i]['result'] = result
                    print("Success")
                except:
                    pkg_data[i]['status'] = 'error'
                    #print(sys.exc_info())
                break

def check_validity(form):
    if 'name' not in form:
        return "Error: no name given"
    #if 'data' not in form:
    #    return "Error: no images were uploaded"
    return ''

def get_package(form):
    id = 'None'
    try:
        id = int(form['id'])
    except:
        return 'Error: the id '+form['id']+' is not valid'
    for package in pkg_data:
        if package['id'] == id:
            if package['status'] != 'finished':
                return package['status']
            else:
                return str(package['result'])
    return 'Error: the id '+form['id']+' does not exist'

def push_package(form, address, hang = False):
    global max_id
    validity = check_validity(form)
    id = max_id
    max_id += 1
    if validity != "":
        return "Invalid dataset: " + validity

    package_type = 'predict'
    timeout = None
    now = time.time()
    if 'type' in form:
        package_type = form['type']
    if hang:
        timeout = form['timeout'] + now
    new_package={'name':form['name'], 'id':id, 'client_ip':address, 'timeout':timeout,
        'type':package_type, 'status':'waiting', 'start':now }
    if pkg_data is None:
        return "Error: server not ready"
    pkg_data.append(new_package)

    for client in clients:
        io.emit('status', list(pkg_data), namespace = '/', room=client)

    if not hang:
        return str(id)
    else:
        while True:
            time.sleep(1)
            result = get_package(form)
            if result not in "waiting running".split():
                return result

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')

@app.route('/status', methods=['GET'])
def status():
    return render_template('status.html', client_mag = len(clients), kernel=kernel.is_alive())

@app.route('/', methods=['POST'])
def receive():
    global pkg_data, max_id

    if 'id' in request.form:
        return get_package(request.form)
    if 'timeout' in request.form and (type(request.form['timeout']) == float or type(request.form['timeout']) == int)\
        and request.form['timeout'] > 0:
        return push_package(request.form, request.remote_addr, hang=True)
    return push_package(request.form, request.remote_addr)

@socketio.on('connected')
def connected():
    global pkg_data, first_connection, clients, kernel
    if first_connection:
        pkg_data = mp.Manager().list()
        kernel = mp.Process(target=run, args=(pkg_data,))
        kernel.daemon = True
        kernel.start()
        first_connection= False

    if request.remote_addr == '127.0.0.1':
        io.emit("debug", 'Confirmed connection')
        io.emit('status', list(pkg_data))
        clients.append(request.sid)

@socketio.on('update')
def update():
    print("Update now")
    io.emit('status', list(pkg_data))
    
@socketio.on('disconnected')
def connected():
    global clients
    if request.remote_addr == '127.0.0.1':
        io.emit("debug", 'Confirmed disconnection')
        clients.remove(request.sid)