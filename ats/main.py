import os
import sys
import io
import time
import json
import subprocess
import logging

from flask import Flask, render_template, request, Response

from dotenv import load_dotenv
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(parent_dir, '.env'))

from .apis import storage_apis
from .trading_job.trading_job_manager import TradingJobManager
from .utils.response_helpers import helpers as response_helpers
from .utils.io.streaming_output_redirector import StreamingOutputRedirector

from contextlib import redirect_stdout

console_stream = io.StringIO()  # In-memory stream for console output

trading_job_manager = TradingJobManager()

app = Flask(__name__)

# Configure console outputs and log records to be streamed out through a URL
output_redirector = StreamingOutputRedirector()
sys.stdout = output_redirector
sys.stderr = output_redirector
logging.basicConfig(stream=output_redirector)

logging.getLogger('werkzeug').setLevel(logging.ERROR)  # Set to a higher level (e.g., ERROR)


@app.route("/portal")
def strategy_tester():
    return render_template('tester.html')

@app.route("/portal/strategy_tester/plot/<job_id>/<plot_id>")
def strategy_tester_plot(job_id, plot_id):
    return render_template('plot.html', job_id=job_id, plot_id=plot_id)

@app.route("/logs")
def logs():
    def generate_log_events():
        while True:
            try:
                new_output = output_redirector.get_output()  # Get current output
                output_redirector.output.truncate(0)  # Clear buffer
                output_redirector.output.seek(0)  # Reset position
                yield new_output  # Yield only new output
                time.sleep(0.1)
            except Exception as e:
                print("Error generating log events: %s", e)
    return Response(generate_log_events(), mimetype="text/event-stream")

@app.route('/trading_job/create', methods=['POST'])
def trading_job_create():
    try:
        job_id = trading_job_manager.create_job(request.get_json())
        return {
            'job_id': job_id
        }
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/trading_job/reload', methods=['POST'])
def trading_job_reload():
    try:
        args = request.get_json()
        return trading_job_manager.reload_job(**args)
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/trading_job/run/<string:job_id>', methods=['GET'])
def trading_job_run(job_id):
    try:
        trading_job_manager.run_job(job_id)
        return {'job_id': job_id, 'message': 'Trading job started.'}
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/trading_job/stop/<string:job_id>', methods=['GET'])
def trading_job_stop(job_id):
    try:
        trading_job_manager.stop_job(job_id)
        return {'job_id': job_id, 'message': 'Trading job stopped.'}
    except Exception as e:
        return response_helpers.exception_to_response(e)

# TODO: Return the configs
@app.route('/trading_job/status/<string:job_id>', methods=['GET'])
def trading_job_get_status(job_id):
    try:
        return trading_job_manager.get_job_status(job_id)
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/trading_job/list', methods=['GET'])
def trading_job_list():
    try:
        return trading_job_manager.get_all_jobs()
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/trading_job/plot_topic_list/<string:job_id>', methods=['GET'])
def plot_topic_list(job_id):
    try:
        return trading_job_manager.get_job_plot_data(job_id).get_topics()
    except Exception as e:
        return response_helpers.exception_to_response(e)


@app.route('/trading_job/plot_topics/<string:job_id>', methods=['POST'])
def plot_topics(job_id):
    try:
        args = request.get_json()
        fig = trading_job_manager.get_job_plot_data(job_id).plot_topics(**args)
        full_html = fig.to_html(full_html=True)
        return full_html
    except Exception as e:
        return response_helpers.exception_to_response(e)

@app.route('/ajax/storage/<action>', methods=['POST'])
def storage(action):
    try:
        # Get the raw POST data as a string
        raw_data = request.data.decode('utf-8')

        # Convert the raw data to a dictionary
        data = json.loads(raw_data)

        if action == 'create':
            return storage_apis.create(data)
        elif action == 'update':
            return storage_apis.update(data['id'], data['val'])
        elif action == 'get':
            return storage_apis.get(data['id'])
        elif action == 'delete':
            return storage_apis.delete(data['id'])
        else:
            return storage_apis.get_list()
    except Exception as e:
        return response_helpers.exception_to_response(e)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT")), debug=False)

