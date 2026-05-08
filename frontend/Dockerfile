# syntax=docker/dockerfile:1.6
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

FROM node:20-alpine AS dev
WORKDIR /app
ENV NODE_ENV=development
# Hostname del backend en red Docker (Compose: servicio `backend`). Sobrescribe en `docker run` si aplica.
ENV BACKEND_INTERNAL_URL=http://backend:8000
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
