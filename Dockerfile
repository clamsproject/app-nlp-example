FROM clamsproject/clams-python:0.5.1

WORKDIR ./app

COPY ./ ./

CMD ["python3", "app.py"]
