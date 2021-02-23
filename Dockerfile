FROM clamsproject/clams-python:0.2.0

COPY ./ ./app
WORKDIR ./app

RUN pip3 install -r requirements.txt

CMD ["python3", "app.py"]
