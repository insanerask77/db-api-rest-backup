# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for PostgreSQL and MongoDB
RUN apt-get update && apt-get install -y \
    gnupg \
    curl \
    && apt-get clean

# Add MongoDB public GPG key
RUN curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
   gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg

# Create the list file for MongoDB
RUN echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/debian bullseye/mongodb-org/6.0 main" | \
    tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# Install postgresql-client and mongodb-database-tools
RUN apt-get update && apt-get install -y \
    postgresql-client \
    mongodb-database-tools \
    && apt-get clean

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the app when the container launches
CMD ["uvicorn", "backup_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
