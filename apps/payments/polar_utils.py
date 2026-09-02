import os
import logging
from polar_sdk import Polar

logger = logging.getLogger(__name__)

def get_polar_client():
    token = os.environ.get('POLAR_API_TOKEN', 'polar_oat_Ym8K4i0cM5SqoOA93oq605gPvrla7g1INECmr1Oj7yB')
    env = os.environ.get('POLAR_ENV', 'sandbox')
    server_name = "sandbox" if env == "sandbox" else "production"
    return Polar(access_token=token, server=server_name)


def get_or_create_polar_customer(email: str, name: str, user_id=None):
    client = get_polar_client()

    email_str = (email or '').strip().lower()
    if not email_str or '@' not in email_str or any(bad in email_str for bad in ['example.com', 'example.org', 'test.com', 'localhost']):
        prefix = email_str.split('@')[0] if '@' in email_str and email_str.split('@')[0] else 'cliente'
        email_str = f"{prefix}@gmail.com"

    name_str = (name or '').strip() or "Cliente"

    # 1. Search customer by email using polar-sdk
    try:
        search_res = client.customers.list(email=email_str)
        if search_res and search_res.result and search_res.result.items:
            cust_id = search_res.result.items[0].id
            logger.info(f"[Polar SDK Customer Found]: ID {cust_id} for email {email_str}")
            return cust_id, email_str
    except Exception as search_err:
        logger.warning(f"[Polar SDK Customer Search Exception]: {search_err}")

    # 2. Create customer if not found using polar-sdk
    try:
        payload = {
            "email": email_str,
            "name": name_str
        }
        if user_id:
            payload["external_id"] = str(user_id)

        created_cust = client.customers.create(request=payload)
        if created_cust and hasattr(created_cust, 'id'):
            cust_id = created_cust.id
            logger.info(f"[Polar SDK Customer Created]: ID {cust_id} for email {email_str}")
            return cust_id, email_str
    except Exception as create_err:
        logger.warning(f"[Polar SDK Customer Creation Exception]: {create_err}")

    # 3. Fallback search by email again
    try:
        search_res2 = client.customers.list(email=email_str)
        if search_res2 and search_res2.result and search_res2.result.items:
            return search_res2.result.items[0].id, email_str
    except Exception:
        pass

    return None, email_str


def create_polar_checkout(order_id, user, total_cost, card_email=None, card_name=None, success_url=None, return_url=None, currency='usd'):
    client = get_polar_client()
    product_id = os.environ.get('POLAR_PRODUCT_ID', '47138fa6-4b35-4e43-9701-d39a08e94bd8')

    try:
        cost_float = float(total_cost)
    except (ValueError, TypeError):
        cost_float = 3.50

    amount_cents = int(round(cost_float * 100))
    if amount_cents < 100:
        amount_cents = 100  # Minimum $1.00 for Polar

    raw_email = card_email or getattr(user, 'email', '') or ''
    raw_name = card_name or (user.get_full_name() if hasattr(user, 'get_full_name') else '') or getattr(user, 'username', '') or 'Cliente'

    user_id = getattr(user, 'id', None)
    customer_id, clean_email = get_or_create_polar_customer(raw_email, raw_name, user_id=user_id)

    valid_success_url = success_url if success_url and success_url.startswith(('http://', 'https://')) else "https://delivery.api.softnow.info/api/v1/payments/success?checkout_id={CHECKOUT_ID}"
    valid_return_url = return_url if return_url and return_url.startswith(('http://', 'https://')) else "https://delivery.api.softnow.info/api/v1/payments/cancel"

    req_payload = {
        "products": [product_id],
        "amount": amount_cents,  # Explicit integer value in cents
        "currency": (currency or 'usd').lower(),
        "customer_email": clean_email,
        "customer_name": raw_name,
        "metadata": {
            "order_id": str(order_id)
        },
        "success_url": valid_success_url,
        "return_url": valid_return_url
    }

    if customer_id:
        req_payload["customer_id"] = customer_id

    logger.info(f"[Polar SDK Checkout Creating] Order #{order_id} | Amount Cents: {amount_cents} (int) | Customer: {customer_id} ({clean_email})")

    chk = client.checkouts.create(request=req_payload)

    chk_dict = {
        "id": chk.id,
        "url": chk.url,
        "amount": getattr(chk, 'amount', amount_cents),
        "currency": getattr(chk, 'currency', currency),
        "status": getattr(chk, 'status', 'open'),
        "customer_id": customer_id,
        "customer_email": clean_email,
        "customer_name": raw_name
    }
    logger.info(f"[Polar SDK Checkout Created Success]: ID {chk.id} | URL {chk.url}")
    return chk_dict
