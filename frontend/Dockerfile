FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_UPSTREAM=http://backend:8000
EXPOSE 80
# Official nginx image runs envsubst on /etc/nginx/templates via docker-entrypoint
CMD ["nginx", "-g", "daemon off;"]
