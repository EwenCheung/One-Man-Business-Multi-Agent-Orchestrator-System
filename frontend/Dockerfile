# Use the official Node image
FROM node:24-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the rest
COPY . .

# Expose Next.js Port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]
