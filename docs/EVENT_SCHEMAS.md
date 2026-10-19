# Event Schemas

Exchange: `quickbite.orders` (durable topic).
Queues/bindings:
- payment.queue → order.created
- restaurant.queue → order.paid
- delivery.queue → order.confirmed
- notification.queue → order.# (multi-segment)

Dead letter: `quickbite.dead` (direct) → `orders.dead-letter.queue` (routing key `failed`).

Events: order.created, order.paid, order.payment.failed, order.confirmed, order.driver.assigned, order.failed.

Envelope fields: event_id, schema_version, event_type, order_id, order_version, occurred_at (UTC ISO-8601), correlation_id, causation_id, data. Persistent delivery mode, JSON content type, AMQP message_id = event_id. Event IDs preserved across retries.
