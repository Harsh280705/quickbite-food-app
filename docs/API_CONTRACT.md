# API Contract

Base: `/api/v1`. Auth: `Authorization: Bearer <token>`.

Endpoints:
- POST /auth/login → {access_token, expires_in, user}
- GET /me
- GET /restaurants?page&page_size
- GET /restaurants/{id}/menu?page&page_size
- POST /orders (requires Idempotency-Key) → 202 {order_id,status,total_amount_minor,currency,version,detail}, Location header
- GET /orders?page&page_size&status
- GET /orders/{id}
- GET /orders/{id}/history?page&page_size
- GET /orders/{id}/notifications?page&page_size
- GET /notifications?page&page_size
- GET /admin/orders?page&page_size&status&customer_email (admin)
- GET /admin/summary (admin)
- GET /health/live, /health/ready

Pagination response: {items,page,page_size,total}. Max page_size 100.
Errors: {code,message,details,request_id}. Statuses: 401/403/404/409/422.
OpenAPI: /api/v1/docs, /api/v1/openapi.json
