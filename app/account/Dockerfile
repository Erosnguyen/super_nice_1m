FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY account_service.py .
COPY .env .

EXPOSE 5004

CMD ["python", "account_service.py"]
