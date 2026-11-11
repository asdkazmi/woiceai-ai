FROM public.ecr.aws/lambda/python:3.9

RUN yum update -y && yum install amazon-linux-extras -y && PYTHON=python2 amazon-linux-extras install epel -y

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src .
COPY .env .

CMD [ "handler.lambda_handler"]