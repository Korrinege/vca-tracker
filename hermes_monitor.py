#!/usr/bin/env python3
"""Check one exact Hermes UK product; notify only, never add to cart."""
import argparse
import json
import os
import re
import smtplib
import ssl
import sys
import time
import unicodedata
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

PRODUCT_REF = "H085956CC18"
PRODUCT_URL = "https://www.hermes.com/uk/en/product/lindy-ii-mini-bag-H085956CC18/"
PRODUCT_NAME = "Hermes UK | Lindy II mini bag | Etoupe | H085956CC18"
SHOT = Path("hermes_last_check.png")
OUT_TEXT = "Unfortunately this product is no longer available"


def log(message):
    print(message, flush=True)


def normalize(text):
    return " ".join("".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    ).lower().split())


def classify(url, text, heading, cart_enabled, unavailable):
    """A visible, enabled button alone is not proof of stock."""
    parsed = urlparse(url)
    expected = urlparse(PRODUCT_URL)
    if parsed.hostname != expected.hostname or parsed.path.rstrip("/") != expected.path.rstrip("/"):
        return "UNKNOWN"
    body = normalize(text)
    if any(marker in body for marker in (
        "restricted access", "access denied", "verify you are human",
        "unusual activity", "temporarily blocked", "captcha",
    )):
        return "UNKNOWN"
    if normalize(heading) != "lindy ii mini bag":
        return "UNKNOWN"
    if not re.search(r"product reference\s*:?\s*" + PRODUCT_REF.lower() + r"\b", body):
        return "UNKNOWN"
    if not re.search(r"colou?r\s*,?\s*:?\s*etoupe\s+selected\b", body):
        return "UNKNOWN"
    # Sold-out text takes precedence over a leftover cart button.
    if unavailable:
        return "OUT_OF_STOCK"
    return "IN_STOCK" if cart_enabled else "UNKNOWN"


def any_visible(locator, enabled=False):
    return any(el.is_visible() and (not enabled or el.is_enabled())
               for el in locator.all())


def check_stock():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-GB", viewport={"width": 1440, "height": 1000})
        try:
            response = page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=60000)
            log("Final URL: " + page.url)
            if response:
                log("HTTP status: " + str(response.status))
                if response.status >= 400:
                    return "UNKNOWN"
            # No CAPTCHA solving, proxy switching, or automated cart actions.
            for label in ("Accept all cookies", "Accept all", "Allow all cookies"):
                button = page.get_by_role("button", name=label, exact=True)
                if button.count() == 1 and button.is_visible():
                    button.click(timeout=5000)
                    break
            cart = page.get_by_role("button", name=re.compile(r"^\s*add to (cart|bag)\s*$", re.I))
            sold_out = page.get_by_text(OUT_TEXT, exact=False)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if any_visible(cart) or any_visible(sold_out):
                    break
                page.wait_for_timeout(1000)
            # Let hydration settle, then require two matching observations.
            page.wait_for_timeout(5000)
            observations = []
            for _ in range(2):
                headings = page.locator("h1").all_text_contents()
                heading = next((s for s in headings if normalize(s) == "lindy ii mini bag"), "")
                observations.append(classify(
                    page.url, page.locator("body").inner_text(), heading,
                    any_visible(cart, enabled=True), any_visible(sold_out),
                ))
                page.wait_for_timeout(3000)
            log("Observations: " + ", ".join(observations))
            return observations[0] if observations[0] == observations[1] else "UNKNOWN"
        finally:
            try:
                page.screenshot(path=str(SHOT), full_page=True, timeout=10000)
            except Exception:
                log("Screenshot unavailable")
            browser.close()


def send_bark(title, body):
    raw = os.environ.get("BARK_KEY", "").strip()
    if not raw:
        log("Bark: BARK_KEY not configured")
        return False
    key = urlparse(raw).path.strip("/").split("/")[0] if raw.startswith(("http://", "https://")) else raw.strip("/")
    # Normal notifications respect iPhone silent mode. No repeating alarm.
    payload = json.dumps({
        "device_key": key, "title": title, "body": body,
        "level": "active", "url": PRODUCT_URL, "group": "Hermes",
    }).encode("utf-8")
    request = urllib.request.Request("https://api.day.app/push", data=payload,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
        ok = result.get("code") == 200
        log("Bark: " + ("sent" if ok else "failed"))
        return ok
    except Exception as error:
        # Avoid logging the device key or request URL.
        log("Bark error: " + type(error).__name__)
        return False


def send_email(subject, body, screenshot=False):
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not user or not password:
        log("Email: Gmail secrets not configured")
        return False
    message = EmailMessage()
    message["From"] = user
    message["To"] = os.environ.get("TO_EMAIL", "").strip() or user
    message["Subject"] = subject
    message.set_content(body + "\n\n" + PRODUCT_NAME + "\n" + PRODUCT_URL)
    if screenshot and SHOT.exists():
        message.add_attachment(SHOT.read_bytes(), maintype="image", subtype="png", filename=SHOT.name)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30, context=ssl.create_default_context()) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
        log("Email: sent")
        return True
    except Exception as error:
        log("Email error: " + type(error).__name__)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-email", action="store_true")
    args = parser.parse_args()
    if args.test_email:
        bark_ok = send_bark("Hermes UK test", "Lindy II mini | Etoupe | H085956CC18")
        email_ok = send_email("Hermes UK test", "Notification test only; stock was not checked.")
        return 0 if bark_ok and email_ok else 1
    log("Checking: " + PRODUCT_NAME)
    try:
        status = check_stock()
    except Exception as error:
        log("Check error: " + type(error).__name__)
        status = "UNKNOWN"
    log("Status: " + status)
    if status == "IN_STOCK":
        bark_ok = send_bark("Hermes UK: Lindy II mini may be available", "Etoupe | H085956CC18 | Tap to verify and purchase")
        email_ok = send_email("Hermes UK: Lindy II mini may be available", "An enabled Add to cart button was visible in two observations. Verify availability on the website.", screenshot=True)
        return 0 if bark_ok and email_ok else 1
    return 1 if status == "UNKNOWN" else 0


if __name__ == "__main__":
    sys.exit(main())
