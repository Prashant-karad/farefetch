import time

import httpx

from app.config import settings


class PayPalError(Exception):
    pass


_http = httpx.AsyncClient(base_url=settings.paypal_base_url, timeout=20.0)
_token: str | None = None
_token_expires_at = 0.0


async def _access_token() -> str:
    """OAuth2 client-credentials: trade our Client ID + Secret for a short-lived access token.
    Cached in memory and refreshed a minute before it expires."""
    global _token, _token_expires_at
    if _token and time.monotonic() < _token_expires_at - 60:
        return _token
    resp = await _http.post(
        "/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
    )
    if resp.status_code != 200:
        raise PayPalError(f"PayPal auth failed: {resp.status_code} {resp.text}")
    body = resp.json()
    _token = body["access_token"]
    _token_expires_at = time.monotonic() + body["expires_in"]
    return _token


async def _request(method: str, path: str, *, json: dict | None = None, request_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {await _access_token()}", "Content-Type": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id  # PayPal's idempotency key
    resp = await _http.request(method, path, json=json, headers=headers)
    if resp.status_code >= 400:
        raise PayPalError(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp.json() if resp.content else {}


async def create_order(*, topup_id: str, amount_value: str, return_url: str, cancel_url: str) -> dict:
    return await _request(
        "POST",
        "/v2/checkout/orders",
        request_id=f"order-{topup_id}",
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": topup_id,
                "custom_id": topup_id,
                "description": "Fairfetch agent wallet top-up",
                "amount": {"currency_code": "USD", "value": amount_value},
            }],
            "payment_source": {"paypal": {"experience_context": {
                "brand_name": "Fairfetch",
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
                "return_url": return_url,
                "cancel_url": cancel_url,
            }}},
        },
    )


async def capture_order(order_id: str) -> dict:
    return await _request("POST", f"/v2/checkout/orders/{order_id}/capture", json={},
                          request_id=f"capture-{order_id}")


def approval_link(order: dict) -> str:
    for link in order.get("links", []):
        if link.get("rel") in ("payer-action", "approve"):
            return link["href"]
    raise PayPalError("PayPal order has no approval link")