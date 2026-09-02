import os
import logging
import requests

logger = logging.getLogger(__name__)

def get_polar_config():
    token = os.environ.get('POLAR_API_TOKEN', 'polar_oat_Ym8K4i0cM5SqoOA93oq605gPvrla7g1INECmr1Oj7yB')
    product_id = os.environ.get('POLAR_PRODUCT_ID', '47138fa6-4b35-4e43-9701-d39a08e94bd8')
    env = os.environ.get('POLAR_ENV', 'sandbox')
    base_url = "https://sandbox-api.polar.sh/v1" if env == "sandbox" else "https://api.polar.sh/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    return token, product_id, base_url, headers


def get_or_create_polar_customer(email: str, name: str, user_id=None):
    token, product_id, base_url, headers = get_polar_config()

    email_str = (email or '').strip().lower()
    if not email_str or '@' not in email_str or any(bad in email_str for bad in ['example.com', 'example.org', 'test.com', 'localhost']):
        prefix = email_str.split('@')[0] if '@' in email_str and email_str.split('@')[0] else 'cliente'
        email_str = f"{prefix}@gmail.com"

    name_str = (name or '').strip() or "Cliente"

    # 1. Search customer by email
    try:
        search_res = requests.get(f"{base_url}/customers/?email={email_str}", headers=headers)
        if search_res.status_code == 200:
            items = search_res.json().get("items", [])
            if items:
                cust_id = items[0].get("id")
                logger.info(f"[Polar Customer Found]: ID {cust_id} for email {email_str}")
                return cust_id, email_str
    except Exception as search_err:
        logger.warning(f"[Polar Customer Search Exception]: {search_err}")

    # 2. Create customer if not found
    try:
        payload = {
            "email": email_str,
            "name": name_str
        }
        if user_id:
            payload["external_id"] = str(user_id)

        create_res = requests.post(f"{base_url}/customers/", headers=headers, json=payload)
        if create_res.status_code in [200, 201]:
            cust_id = create_res.json().get("id")
            logger.info(f"[Polar Customer Created]: ID {cust_id} for email {email_str}")
            return cust_id, email_str
        else:
            logger.warning(f"[Polar Customer Creation Failed Status {create_res.status_code}]: {create_res.text}")
    except Exception as create_err:
        logger.warning(f"[Polar Customer Creation Exception]: {create_err}")

    # 3. Fallback search by email again
    try:
        search_res2 = requests.get(f"{base_url}/customers/?email={email_str}", headers=headers)
        if search_res2.status_code == 200:
            items = search_res2.json().get("items", [])
            if items:
                return items[0].get("id"), email_str
    except Exception:
        pass

    return None, email_str


def create_polar_checkout(order_id, user, total_cost, card_email=None, card_name=None, success_url=None, return_url=None, currency='usd'):
    token, product_id, base_url, headers = get_polar_config()

    # Calculate amount in cents as an INTEGER (e.g. $12.50 -> 1250)
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

    payload = {
        "products": [product_id],
        "amount": amount_cents,  # Explicit integer value in cents (e.g. 1575 for $15.75)
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
        payload["customer_id"] = customer_id

    logger.info(f"[Polar Checkout Creating] Order #{order_id} | Amount Cents: {amount_cents} (int) | Customer: {customer_id} ({clean_email})")

    res = requests.post(f"{base_url}/checkouts/", headers=headers, json=payload)
    if res.status_code in [200, 201]:
        chk_data = res.json()
        logger.info(f"[Polar Checkout Created Success]: ID {chk_data.get('id')} | URL {chk_data.get('url')}")
        return chk_data
    else:
        err_msg = f"Error de Polar ({res.status_code}): {res.text}"
        logger.error(f"[Polar Checkout Creation Failed]: {err_msg}")
        raise ValueError(err_msg)
