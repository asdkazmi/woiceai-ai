import sys
sys.path.append('../src')

from dotenv import load_dotenv
load_dotenv()

import logging
import json
from flask import Flask, request
from flask_restful import Api, Resource

from src.handler import lambda_handler

app = Flask(__name__)
api = Api(app)

# Configure the logging system
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class woice_chat(Resource):

    def post(self):
        return lambda_handler(json.loads(request.data), [])


# Add the resource to the API
api.add_resource(woice_chat, '/chat')

if __name__ == "__main__":
    app.run(debug=False)
