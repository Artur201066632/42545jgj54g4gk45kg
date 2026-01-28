FROM python:3.11-slim

WORKDIR /app

# Копіюємо файли залежностей
COPY requirements.txt .

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код
COPY . .

# Створюємо папку для даних
RUN mkdir -p data

# Запускаємо бота
CMD ["python", "bot.py"]
