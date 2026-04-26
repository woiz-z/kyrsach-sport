FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

RUN printf 'server {\n    listen NGINX_PORT;\n    location / {\n        root /usr/share/nginx/html;\n        try_files $uri $uri/ /index.html;\n        add_header Cache-Control "no-store, no-cache";\n    }\n}\n' > /etc/nginx/conf.d/default.conf.template

EXPOSE 80
CMD ["sh", "-c", "sed 's/NGINX_PORT/'\"${PORT:-80}\"'/g' /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
