FROM python:3.12-slim

ENV ROOT_DIR=/app
ENV PYTHONPATH=${ROOT_DIR}

WORKDIR ${ROOT_DIR}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

CMD ["./start.sh"]
