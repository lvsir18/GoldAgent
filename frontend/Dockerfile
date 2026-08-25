FROM node:22-alpine AS deps
WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm config set registry "$NPM_REGISTRY" && \
    npm ci --prefer-offline \
      --maxsockets=3 \
      --fetch-retries=5 \
      --fetch-retry-mintimeout=20000 \
      --fetch-retry-maxtimeout=120000

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend ./
ENV BACKEND_URL=http://backend:8080
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 BACKEND_URL=http://backend:8080
RUN addgroup -S goldagent && adduser -S goldagent -G goldagent
COPY --from=build --chown=goldagent:goldagent /app/.next/standalone ./
COPY --from=build --chown=goldagent:goldagent /app/.next/static ./.next/static
COPY --from=build --chown=goldagent:goldagent /app/public ./public
USER goldagent
EXPOSE 3000
CMD ["node", "server.js"]
