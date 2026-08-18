
import os

import htcondor2 as htcondor

from flask import Flask
from flask_apscheduler import APScheduler

import htcondor_autoscale_manager.occupancy_metric
import htcondor_autoscale_manager.patch_annotation

from contextlib import contextmanager
from tempfile import TemporaryDirectory
from pathlib import Path
import shutil

app = Flask(__name__)

config = {}
for key, val in os.environ.items():
    if key.startswith("FLASK_"):
        app.config[key[6:]] = val

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

g_metric = 1.0


def bearer_token_context(app):
    ''' Helper function that creates an HTCondor Security Context 
    based on a bearer token specified via app or env config
    '''
    bearer_tkn = app.config.get("BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
    bearer_tkn_file = app.config.get('BEARER_TOKEN_FILE') or os.environ.get('BEARER_TOKEN_FILE') 
    
    if bearer_tkn:
        return htcondor.SecurityContext(token=bearer_tkn)
    elif bearer_tkn_file:
        with open(bearer_tkn_file, 'r') as f:
            token = f.read().strip()
            return htcondor.SecurityContext(token=token)
        

@scheduler.task("interval", id="metric_update", seconds=60)
def metric_update():
    resource = app.config.get("RESOURCE_NAME")
    if not resource:
        print("RESOURCE_NAME not set - cannot compute metric.")
        return
    query = app.config.get("POD_LABEL_SELECTOR")
    if not query:
        print("POD_LABEL_SELECTOR not set - cannot query kubernetes for pods.")
        return

    scale_param = {'velocity': int(app.config.get("SCALE_VELOCITY", 1)),
                   'idlepods': int(app.config.get("IDLE_PODS", 0))}

    try:
        global g_metric
        security = bearer_token_context(app)
        g_metric, counts = htcondor_autoscale_manager.occupancy_metric(query, resource, scale_param, security_context=security)
    except Exception as exc:
        print(f"Exception occurred during metric update: {exc}")
        return

    # Annotate the 'cost' of deleting the pod.  We only want to patch
    # for changes (which might include when the job originally starts).
    for pod, current_cost in counts['costs'].items():
        desired_cost = 10
        if pod not in counts['online_pods']:
            desired_cost = 0
        elif pod in counts['idle_pods']:
            desired_cost = 5
        if desired_cost != current_cost:
            htcondor_autoscale_manager.patch_annotation(pod, desired_cost)

@app.route("/metrics")
def metrics():
    return f"occupancy {g_metric}\n"

def entry():
    app.run()
