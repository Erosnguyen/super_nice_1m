FROM python:3.9
WORKDIR /app
COPY visualization_service.py .
RUN pip install flask pandas plotly requests 
CMD ["python", "visualization_service.py"]
