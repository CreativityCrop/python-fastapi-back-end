FROM python:3.9
WORKDIR /creativitycrop-api
RUN apt-get update
RUN apt-get install nano iputils-ping redis-tools -y
COPY ./requirements.txt /creativitycrop-api/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /creativitycrop-api/requirements.txt
COPY ./app /creativitycrop-api/app
COPY ./main.py /creativitycrop-api/main.py
EXPOSE 8000
#CMD ["python", "main.py"]
CMD exec python main.py > app.log 2>&1
