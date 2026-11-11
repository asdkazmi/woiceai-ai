FROM public.ecr.aws/lambda/python:3.6

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN pip install "pymongo[srv]"

RUN curl -SL https://chromedriver.storage.googleapis.com/2.37/chromedriver_linux64.zip > chromedriver.zip &&  \
    curl -SL https://github.com/adieuadieu/serverless-chrome/releases/download/v1.0.0-37/stable-headless-chromium-amazonlinux-2017-03.zip > headless-chromium.zip
RUN unzip chromedriver.zip -d /bin/ && unzip headless-chromium.zip -d /bin/ && rm headless-chromium.zip chromedriver.zip

COPY src .
COPY .env .

ENV TRANSFORMERS_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1

CMD [ "handler.scrapper" ]