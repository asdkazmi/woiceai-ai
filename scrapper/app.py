import json
import logging
import os
import sys

from flask import Flask
from flask_restful import Api, Resource, request

from src.handler import scrapper

sys.path.insert(1, os.path.dirname(__file__))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = Flask(__name__)
api = Api(app)


class Scrap(Resource):

    def post(self):
        return scrapper(json.loads(request.data), [])


# Add the resource to the API
api.add_resource(Scrap, '/scrapper')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
