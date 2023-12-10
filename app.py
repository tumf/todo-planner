import logging
from flask import Flask, request
from todo_planner.main import event_handler

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def todoist_webhook():
    event = request.get_json()
    logging.info('Request: {}'.format(event))
    event_handler(event)
    return "Webhook received", 200


if __name__ == '__main__':
    app.run(debug=True)
