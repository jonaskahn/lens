ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-slim-bookworm AS base

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@11 --activate

WORKDIR /app

FROM base AS build-deps
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
COPY --from=build-deps /app/node_modules ./node_modules
COPY apps/web/ ./
ENV NUXT_API_BASE_URL=http://api:8000/api/v1
RUN pnpm run build

FROM node:${NODE_VERSION}-slim-bookworm AS runtime

WORKDIR /app

COPY --from=build /app/.output ./.output

ENV NITRO_HOST=0.0.0.0
ENV NITRO_PORT=3000
ENV NUXT_API_BASE_URL=http://api:8000/api/v1

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
