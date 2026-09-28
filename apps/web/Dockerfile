FROM node:20-alpine AS builder
RUN npm install -g pnpm@10.27.0
WORKDIR /app
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/
RUN cd apps/web && pnpm install --frozen-lockfile
COPY apps/web/ apps/web/
RUN cd apps/web && pnpm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
