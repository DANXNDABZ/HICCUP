# Use the official Python image

FROM python:3.10-slim



# Set the working directory

WORKDIR /app



# Copy project files

COPY . .



# Install dependencies

RUN pip install --no-cache-dir -r requirements.txt



# Expose port for Flask dashboard (optional)

EXPOSE 5000



# Start the bot

CMD ["python", "main.py"]
