FROM node:24-alpine@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85 AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.6-alpine@sha256:bb8f722b4be005fcd7827816a136ab779fd40185d85b5171be915cc7fc0575c7
RUN apk upgrade --no-cache
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/production/nginx.conf /etc/nginx/nginx.conf
RUN rm /etc/nginx/conf.d/default.conf
USER 101:101
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
EXPOSE 8080
