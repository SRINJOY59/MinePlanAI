# Use Node.js 18 alpine as the base image
FROM node:18-alpine

# Set the working directory in the container
WORKDIR /app

# Copy the package.json and the lock file
COPY frontend/package.json ./

# Install dependencies
RUN npm install

# Copy the frontend source code
COPY frontend .

# Build the Next.js app
RUN npm run build

# Expose the production port
EXPOSE 3000

# Command to run the application in production mode
CMD ["npm", "start"]
