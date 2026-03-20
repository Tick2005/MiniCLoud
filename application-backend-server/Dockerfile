FROM python:3.11-alpine
WORKDIR /app
COPY app.py .
COPY students.json .
RUN pip install --no-cache-dir flask requests python-jose pymysql pandas openpyxl xlrd
EXPOSE 8081
CMD ["python","app.py"]
