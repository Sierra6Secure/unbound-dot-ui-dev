# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install Flask and the Docker SDK
RUN pip install --no-cache-dir flask docker

# Copy the backend and UI files into the /app folder
COPY app/server.py .
COPY app/index.html .

# Copy the entrypoint script to the root and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the port
EXPOSE 80
EXPOSE 5330

# Launch the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]