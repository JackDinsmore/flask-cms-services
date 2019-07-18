'''
This is a server designed to predict on data sent from an arbitrary
client using MNIST. It is intended to be implemented in a Google Kubernetes cluster.

Since this program uses multiprocessing, occasionally errors occur in code that seems
like it should run flawlessly. This occurs when two threads are both accessing the
same data, in which case it can change unpredictably. Since these errors are rare,
my solution is to enclose these error-prone parts of the loop in try-except loops, 
where the except block simply tries the same task again.

I plan to implement a kind of command prompt eventually, where you can send commands
to the server as an admin through the same format as you might send a prediction
request. These commands might be to shutdown the server, stop execution on a certain
dataset or move some in the queue, etc. 
'''

import os, time, sys, ntpath, logging
from flask import Flask, request, render_template
import flask_socketio as io
import multiprocessing as mp
import ml_functions as ml
import numpy as np

global pages, pkg_data, max_id, first_connection, kernel, manager, pkg_data, data_in, results_out
pages = []

# Temporary initializations for shared memory
manager = None
pkg_data = None
data_in = None
results_out = None
kernel = None

max_id=0
first_connection = True

app = Flask(__name__, instance_relative_config=True)
socketio = io.SocketIO(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def initialize():
    global pkg_data, first_connection, kernel, manager, pkg_data, data_in, results_out
    if first_connection:
        manager = mp.Manager()
        pkg_data = manager.list()
        data_in = manager.list()
        results_out = manager.list()
        kernel = mp.Process(target=run, args=(pkg_data, data_in, results_out))
        kernel.daemon = True
        kernel.start()
        first_connection= False
        print("\nINITIALIZED\n")


def convert_to_json(package_data):
    ret = []
    for item in package_data:
        ret.append(dict(item))
    return ret


def run(pkg_data, data_in, results_out):
    while True:
        now = time.time()
        i = 0
        # Do deletions if necessary
        while i < len(pkg_data):
            if pkg_data[i]['timeout'] > 0 and now > pkg_data[i]['timeout']:
                pkg_data[i]['status'] = 'timed out'
            if pkg_data[i]['status'] == 'error' or pkg_data[i]['status'] == 'finished':
                if now > pkg_data[i]['delete']:
                    # Remove package
                    j = 0
                    for package in data_in:
                        if package['id'] == pkg_data[i]['id']:
                            del data_in[j]
                            break
                        j += 1
                    del pkg_data[i]
                    continue
            i += 1

        for i in range(len(pkg_data)):
            if pkg_data[i]['status'] == 'waiting':
                pkg_data[i]['status'] = 'running'
                try:
                    data = None
                    for package in data_in:
                        if package['id'] == pkg_data[i]['id']:
                            data = package['data']
                            break
                    if data is None:
                        raise RuntimeError("The data containers and package containers became desynced")
                    np_array, web_array = ml.predict(data)
                    pkg_data[i]['status'] = 'finished'
                    pkg_data[i]['result'] = web_array
                    pkg_data[i]['delete'] = time.time() + 15
                    for package in results_out:
                        if package['id'] == pkg_data[i]['id']:
                            package['data'] = np_array
                            break
                except:
                    pkg_data[i]['status'] = 'error'
                    pkg_data[i]['error_type'] = str(sys.exc_info()[0].__name__)
                    pkg_data[i]['error_value'] = str(sys.exc_info()[1])
                    tb = sys.exc_info()[2]
                    pkg_data[i]['error_tb'] = ''
                    while tb != None:
                        if ntpath.basename(__file__) == ntpath.basename(tb.tb_frame.f_code.co_filename):
                            pkg_data[i]['error_tb'] += str(tb.tb_lineno) + ' '
                        tb = tb.tb_next
                    if pkg_data[i]['error_tb'][-1] == ' ':
                        pkg_data[i]['error_tb'] = pkg_data[i]['error_tb'][:-1]
                    del tb
                    pkg_data[i]['delete'] = time.time() + 60
                break

def check_validity(form):
    if 'name' not in form:
        return "Error: no name given"
    if 'data' not in form:
        return "Error: no images were uploaded"
    if 'num_samples' not in form:
        return "Error: number of samples was not given"
    try:
        int(form['num_samples'])
    except:
        return "Error: number of samples was not an integer"
    if manager is None or pkg_data is None or results_out is None or data_in is None or kernel is None:
        return "Error: server is not ready"
    return ''

def get_package(form):
    id = 'None'
    if 'id' not in form:
        return 'Error: no ID number was passed'
    try: id = int(form['id'])
    except: return "Error: the ID you provided is not a number"
    for package in pkg_data:
        if package['id'] == id:
            if package['status'] != 'finished':
                return package['status']
            else:
                for result in results_out:
                    if result['id'] == id:
                        return result['data'].tostring().hex()
    return 'Error: the ID '+form['id']+' does not exist'

def push_package(form, address, hang = False):
    global max_id, manager
    validity = check_validity(form)
    id = max_id
    max_id += 1
    if validity != "":
        return "Invalid dataset: " + validity
    now = time.time()
    new_package = manager.dict()
    new_package['name']=form['name']
    new_package['id']=id
    new_package['client_ip']=address
    new_package['status']='waiting'
    new_package['start']=now
    new_package['timeout']=-1
    if 'timeout' in form:
        try:
            new_package['timeout'] = float(form['timeout']) + now
        except: pass

    data = np.frombuffer(bytes.fromhex(form['data']))
    shape = (int(form['num_samples']), 28, 28, 1)
    data = data.reshape(shape)
    data_in.append(manager.dict({'id':id, 'data':data}))
    pkg_data.append(new_package)
    results_out.append(manager.dict({'id':id, 'data':None}))
    for page in pages:
        io.emit('status', convert_to_json(pkg_data), namespace = '/', room=page)

    if not hang:
        return str(id)
    else:
        while True:
            time.sleep(1)
            package_request = {'id':id}
            try:
                result = get_package(package_request)
                if result not in "waiting running".split():
                    return result
            except:
                continue


@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')


@app.route('/status', methods=['GET'])
def status():
    return render_template('status.html', page_mag = len(pages), kernel=kernel.is_alive())


@app.route('/', methods=['POST'])
def receive():
    global pkg_data, max_id

    if 'id' in request.form:
        return get_package(request.form)
    if 'hang' in request.form and request.form['hang']:
        return push_package(request.form, request.remote_addr, hang=True)
    return push_package(request.form, request.remote_addr)

    
@app.route('/error', methods=['GET'])
def error_request():
    id = -1
    try: id = int(request.args.get("id", default=-1))
    except: pass
    for package in pkg_data:
        if package["id"]==id:
            if package["status"] != 'error':
                break
            if "error_type" not in package or "error_value" not in package:
                break
            lines = package["error_tb"].split()
            return render_template('error.html', id=request.args.get("id", default=None),
                type=package["error_type"], value=package["error_value"], traceback=lines,
                quantity = len(lines))
    return render_template('error-invalid-id.html', id=request.args.get("id", default=None))

    
@app.route('/result', methods=['GET'])
def result_request():
    id = -1
    try: id = int(request.args.get("id", default=-1))
    except: pass
    if pkg_data is None:
        render_template('invalid-id.html', id=request.args.get("id", default=None))
    for package in pkg_data:
        if package["id"]==id:
            if package["status"] != 'finished':
                break
            if "result" not in package:
                break
            best_numbers=[]
            for prediction in package["result"]:
                best_numbers.append(prediction.index(max(prediction)))
            return render_template('result.html', id=request.args.get("id", default=None),
                result=package["result"], best=best_numbers, quantity = len(package["result"]))
    return render_template('invalid-id.html', id=request.args.get("id", default=None))


@socketio.on('connected')
def connected():
    initialize()
    global pages
    #if request.remote_addr == '127.0.0.1':
    io.emit("debug", 'Confirmed connection')
    io.emit('status', convert_to_json(pkg_data))
    pages.append(request.sid)


@socketio.on('update')
def update():
    if(pkg_data is not None):
        io.emit('status', convert_to_json(pkg_data))
    
    
@socketio.on('disconnected')
def disconnected():
    global pages
    #if request.remote_addr == '127.0.0.1':
    io.emit("debug", 'Confirmed disconnection')
    pages.remove(request.sid)