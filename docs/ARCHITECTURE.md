# Architecture

QuickBite is a full-stack food delivery order processing system.

- Backend: FastAPI (Python 3.11), SQLAlchemy 2 async, Alembic, PostgreSQL, aio-pika, RabbitMQ.
- Frontend: Flutter (Web/Android/iOS) with Provider state management.
- Messaging: durable topic exchange `quickbite.orders`, 4 workers, transactional outbox, retry scheduler, quarantine + dead-letter.

Flow: Customer checkout → API commits order + history + idempotency + outbox event (202) → outbox dispatcher publishes `order.created` → payment worker → `order.paid` → restaurant worker → `order.confirmed` → delivery worker → `order.driver.assigned`. Notification worker consumes `order.#` and persists notifications without changing status.

Money stored as integer minor units (INR 12.50 = 1250).

## Service and event flow

```mermaid
flowchart LR
    subgraph Clients
      W[Flutter Web]
      A[Flutter Android]
      I[Flutter iOS]
    end
    W -->|HTTPS / local development HTTP| API[FastAPI /api/v1]
    A -->|HTTPS / local development HTTP| API
    I -->|HTTPS / local development HTTP| API
    API <-->|orders, history, idempotency, events| PG[(PostgreSQL)]
    PG -->|pending publications| OB[Outbox dispatcher]
    OB -->|confirmed, mandatory publish| X{{quickbite.orders topic}}
    X -->|order.created| P[Payment worker]
    X -->|order.paid| R[Restaurant worker]
    X -->|order.confirmed| D[Delivery worker]
    X -->|order.#| N[Notification worker]
    P -->|transaction + child event| PG
    R -->|transaction + child event| PG
    D -->|transaction + child event| PG
    N -->|persisted customer notifications| PG
    P -. transient failure .-> RJ[(retry_jobs + targeted outbox)]
    R -. transient failure .-> RJ
    D -. transient failure .-> RJ
    N -. transient failure .-> RJ
    RJ --> RS[Retry scheduler]
    RS -->|due delivery to original queue| Q[Target worker queue]
    P -. exhausted / malformed .-> QO[(quarantine_records)]
    R -. exhausted / malformed .-> QO
    D -. exhausted / malformed .-> QO
    N -. exhausted / malformed .-> QO
    QO --> DX{{quickbite.dead direct}}
    DX --> DLQ[orders.dead-letter.queue]
    API -->|reads current authoritative state| PG
```

RabbitMQ is a transport; PostgreSQL remains the source of truth for order
state. An accepted order can remain `PENDING` while an outbox publication waits
for RabbitMQ recovery. Delivery is at least once, and consumers use
`(consumer_name, event_id)` deduplication so redelivery does not repeat
committed business effects.
