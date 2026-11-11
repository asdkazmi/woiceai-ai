import logging
import json

from flask import Flask
from flask_restful import Api, Resource, request

from src.handler import lambda_handler

app = Flask(__name__)
api = Api(app)

# Configure the logging system
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class woice(Resource):

    def post(self):
        return lambda_handler(json.loads(request.data), [])


# Add the resource to the API
api.add_resource(woice, '/process_files')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
