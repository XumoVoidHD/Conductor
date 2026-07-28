FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html app.js config.js styles.css /usr/share/nginx/html/

EXPOSE 5500

CMD ["nginx", "-g", "daemon off;"]
