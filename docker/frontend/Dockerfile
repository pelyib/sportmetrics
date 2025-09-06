FROM nginx:alpine

# Copy custom nginx config
COPY docker/frontend/nginx.conf /etc/nginx/nginx.conf

# Copy static files
COPY frontend/public/ /usr/share/nginx/html/

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
