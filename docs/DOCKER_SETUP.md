# Docker Setup — QuickBite

## Start full stack
```
docker compose -p quickbite-local up -d --build
```
This builds backend + web images, starts postgres, rabbitmq, api, workers, dispatcher, scheduler, nginx web.

## Migrations
The compose setup does not auto-run migrations. Run once:
```
docker compose -p quickbite-local exec api alembic upgrade head
docker compose -p quickbite-local exec api python scripts/seed.py
```

## URLs
- Web (Nginx): http://localhost:8080
- API via Nginx: http://localhost:8080/api/v1
- API direct: http://localhost:8000
- RabbitMQ mgmt: http://localhost:15672

## Scaling
```
docker compose -p quickbite-local up -d --scale payment-worker=3
```

## Stop
```
docker compose -p quickbite-local down
```
Data persists in named volumes quickbite-local-postgres-data / quickbite-local-rabbitmq-data.

## Notes
- Web uses same-origin /api via Nginx reverse proxy.
- No host postgres/rabbitmq required.
- Ports bound to 127.0.0.1.
