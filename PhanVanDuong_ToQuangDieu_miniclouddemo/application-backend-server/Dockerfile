FROM python:3.11-alpine
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask requests python-jose pymysql
EXPOSE 8081
CMD ["python","app.py"]
