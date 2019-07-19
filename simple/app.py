import os, time, sys, ntpath, logging
from flask import Flask, request, render_template
import flask_socketio as io
import ml_functions as ml
import numpy as np

global pages, pkg_data, max_client_id, id_create_permitted, client_ids, first_connection, pkg_data
pages = []
pkg_data = []
client_ids = {}
max_client_id = 0
id_create_permitted = True

first_connection = True

app = Flask(__name__, instance_relative_config=True)
socketio = io.SocketIO(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def create_client_id(address):
    global max_client_id, id_create_permitted, client_ids
    while not id_create_permitted:
        pass # This way, only one client can create an id at a time
    id_create_permitted = False
    client_ids[address] = {'id':max_client_id, 'max_id':0}
    max_client_id += 1
    id_create_permitted = True


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
    return ''

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')


@app.route('/status', methods=['GET'])
def status():
    return render_template('status.html', page_mag=len(pages), client_ids=client_ids.items(), client_num=len(client_ids))


@app.route('/', methods=['POST'])
def receive():
    global pkg_data, client_ids
    if 'id' in request.form:
        # Get status
        pass
    if not request.remote_addr in client_ids:# ASSUMES ONE CLIENT PER IP
        create_client_id(request.remote_addr)
    client_id = client_ids[request.remote_addr]['id']
    client_max_id = client_ids[request.remote_addr]['max_id']
    validity = check_validity(request.form)
    id = str(client_id)+'-'+str(client_max_id)
    client_ids[request.remote_addr]['max_id'] += 1
    if validity != "":
        return "Invalid dataset: " + validity
    now = time.time()
    new_package = {}
    new_package['name']=request.form['name']
    new_package['id']=id
    new_package['status']='running'
    new_package['start']=now
    new_package['timeout']=-1
    if 'timeout' in request.form:
        try:
            new_package['timeout'] = float(request.form['timeout']) + now
        except ValueError: pass # timeout is not a float

    data = np.frombuffer(bytes.fromhex(request.form['data']))
    data = data.reshape((int(request.form['num_samples']), 28, 28, 1))
    pkg_data.append(new_package)
    for page in pages:
        io.emit('status', pkg_data, namespace = '/', room=page)

    ret = None
    if True:#try:
        np_array, web_array  = ml.predict(data)
        for package in pkg_data:
            if package['id'] == id:
                # post the result
                package['status']='finished'
                package['result'] = web_array
                result_return = np_array.tostring().hex()
                ret = result_return
    '''except:
        for package in pkg_data:
            if package['id'] == id:
                # post the error messages
                package['status']='error'
                package['error_type'] = str(sys.exc_info()[0].__name__)
                package['error_value'] = str(sys.exc_info()[1])
                tb = sys.exc_info()[2]
                package['error_tb'] = ''
                while tb != None:
                    if ntpath.basename(__file__) == ntpath.basename(tb.tb_frame.f_code.co_filename):
                        package['error_tb'] += str(tb.tb_lineno) + ' '
                    tb = tb.tb_next
                if package['error_tb'][-1] == ' ':
                    package['error_tb'] = package['error_tb'][:-1]
                del tb
                package['delete'] = time.time() + 60
                ret = 'Error'''

    for page in pages:
        io.emit('status', pkg_data, namespace = '/', room=page)
    if ret is None:
        return "Error: package tracker became desynced"
    return ret
    
@app.route('/error', methods=['GET'])
def error_request():
    id = 'null-id'
    try: id = request.args.get("id", default='null-id')
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
    id = 'null-id'
    try: id = int(request.args.get("id", default='null-id'))
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
    global pages
    #if request.remote_addr == '127.0.0.1':
    io.emit("debug", 'Confirmed connection')
    io.emit('status', pkg_data)
    pages.append(request.sid)


@socketio.on('update')
def update():
    io.emit('status', pkg_data)
    
@socketio.on('disconnected')
def disconnected():
    global pages
    #if request.remote_addr == '127.0.0.1':
    io.emit("debug", 'Confirmed disconnection')
    pages.remove(request.sid)