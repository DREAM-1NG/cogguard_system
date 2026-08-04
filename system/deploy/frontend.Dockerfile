FROM node:24-alpine AS frontend-build

WORKDIR /workspace/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

ENV BACKEND_ORIGIN=http://host.docker.internal:8000

COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=frontend-build /workspace/frontend/dist /usr/share/nginx/html

EXPOSE 80
