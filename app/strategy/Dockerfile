FROM python:3.9
WORKDIR /app
COPY strategy_service.py .
RUN pip install flask pandas aiohttp
CMD ["python", "strategy_service.py"]
