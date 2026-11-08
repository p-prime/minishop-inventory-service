# API contract
Generated OpenAPI: openapi.json. Interactive documentation: /docs.
| Method | Path | Input | Result |
|---|---|---|---|
| GET | /health | Path parameters where present | JSON resource |
| GET | /ready | Path parameters where present | JSON resource |
| GET | /products | Path parameters where present | JSON resource |
| POST | /products | JSON body; see OpenAPI | JSON resource |
| GET | /products/{pid} | Path parameters where present | JSON resource |
| GET | /products/{pid}/stock | Path parameters where present | JSON resource |
| PATCH | /products/{pid}/stock | JSON body; see OpenAPI | JSON resource |
| POST | /reservations | JSON body; see OpenAPI | See state rules below |
| GET | /reservations/{rid} | Path parameters where present | See state rules below |
| POST | /reservations/{rid}/release | Path parameters where present | See state rules below |

Product: {"name":"Notebook","stock":10}; stock PATCH: {"delta":5} (additive, not idempotent). Product create returns 201; queries/updates return 200; missing resources 404; negative stock/conflicts 409; invalid input 422.
Reservation: {"reservation_id":"stable-id","items":[{"product_id":"product-id","quantity":3}]}. Returns 200 with id/status. Insufficient or unknown product yields REJECTED (200); Order maps this business rejection to 409. Same ID with changed items yields 409. RESERVED or REJECTED is durable. RESERVED -> RELEASED; release replay does not add stock again. RELEASED never re-reserves. Rejected requests remain rejected even after restocking: use a new ID.
Reservation release is an internal administrative demonstration endpoint. Never release reservations backing a confirmed order. No customer cancellation flow exists. Deployment is restricted to a trusted local demonstration; authentication is outside scope.
