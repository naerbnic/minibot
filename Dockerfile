FROM python:3.7 as builder

RUN mkdir /install
WORKDIR /install

COPY requirements.txt /requirements.txt

RUN pip install --install-option="--prefix=/install" -r /requirements.txt

FROM python:3.7-alpine

COPY --from=builder /install /usr/local
COPY . /app

WORKDIR /app

RUN pip install .

EXPOSE 8080

CMD ["run_minibot_server"]