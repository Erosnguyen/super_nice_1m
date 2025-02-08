FROM python:3.9
WORKDIR /app
COPY data_service.py .
RUN pip install flask aiohttp pandas
CMD ["python", "data_service.py"]
