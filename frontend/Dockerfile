FROM node:24-slim

WORKDIR /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5180

ENTRYPOINT ["sh", "/usr/local/bin/docker-entrypoint.sh"]
