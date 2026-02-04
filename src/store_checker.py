#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import json
import os
import sys
import time
from datetime import datetime

import crayons
import requests
import smtplib, ssl
TELEGRAM_BOT_TOKEN = "" ## Add here or use os.environ.get()
TELEGRAM_CHAT_ID = ""  #Add here or use os.environ.get()


def send_telegram_alert(available_items, bot_token, chat_id):
    messages = []
    for store_name, items in available_items.items():
        items_text = "\n".join([f"• {item}" for item in items])
        messages.append(f"{store_name}:\n{items_text}")
    
    full_message = " iPhone Stock Alert \n\nThe following iPhones are now available:\n\n"
    full_message += "\n\n".join(messages)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": full_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, data=data)
    

## Optional
def send_email_alert():
    port = 465
    smtp_server = "smtp.gmail.com"
    sender_email = "" ## Add here
    receiver_email = "" ## Add here
    password = ""  # get this from Google account security (App passwords)

    message = """\
    Subject: Iphone *** 

    Your iPhone is available at your selected Apple Store!"""

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)


class Configuration:
    """Load the configuration from the config, country, device family, zip, models to search for."""

    def __init__(self, filename,selected_models):
        if filename is None:
            print("No configuration was provided.")
            exit(0)
        with open("config.json") as json_data_file:
            config = json.load(json_data_file)

        self.country_code = config.get("country_code")
        self.device_family = config.get("device_family")
        self.zip_code = config.get("zip_code", [])
        self.selected_device_models = selected_models
        self.selected_carriers = config.get("carriers", [])
        self.selected_stores = config.get("stores", [])
        # Store numbers are available here.
        self.appointment_stores = config.get("appointment_stores", [])


class StoreChecker:
    """Class to handle store checking and fetching and processing of stock of apple products."""
    
    # Base URL is the apple's URL used to make product links and also API
    # calls. Country code is needed only for non-US countries.
    APPLE_BASE_URL = "https://www.apple.com/{0}/"
    # End point for searching for all possible product combinations in the
    # given product family.
    PRODUCT_LOCATOR_URL = "{0}shop/product-locator-meta?family={1}"
    # End point for searching for pickup state of a certain model at a certain
    # location.
    PRODUCT_AVAILABILITY_URL = "{0}shop/retail/pickup-message?pl=true&parts.0={1}&location={2}"
    # URL for the store availabile
    STORE_APPOINTMENT_AVAILABILITY_URL = (
        "https://retail-pz.cdn-apple.com/product-zone-prod/availability/{0}/{1}/availability.json"
    )

    def __init__(self, filename="config.json", selected_models =None):
        """Initialize the configuration for checking store(s) for stock."""

        self.configuration = Configuration(filename, selected_models)
        self.stores_list_with_stock = {}
        self.base_url = "https://www.apple.com/"

        # Since the URL only needs country code for non-US countries, switch
        # the URL for country == US.
        if self.configuration.country_code.upper() != "US":
            self.base_url = self.APPLE_BASE_URL.format(self.configuration.country_code)

    def refresh(self):
        """Refresh information about the stock that is available on the Apple website."""
        device_list = self.find_devices()
        # Exit if no device was found.
        if not device_list:
            print("{}".format(crayons.red("✖  No device matching your configuration was found!")))
            exit(1)
        else:
            print(
                "{} {} {}".format(
                    crayons.green("✔  Found"), len(device_list), crayons.green("devices matching your config.")
                )
            )

        # Downloading the list of products from the server.
        print("{}".format(crayons.blue("➜  Downloading Stock Information for the devices...\n")))

        self.stores_list_with_stock = {}
        for device in device_list:
            self.check_stores_for_device(device)
            time.sleep(1)

        # Get all the stores and sort it by the sequence.
        stores = list(self.stores_list_with_stock.values())
        stores.sort(key=lambda k: k["sequence"])

        # Boolean indicating if the stock is available for any of the items
        # requested (used to play the sound)
        stock_available = False
        all_telegram_items = {}
        # Go through the stores and fetch the stock for all the devices/parts
        # in the store and print their status.
        for store in stores:
            print(
                "\n\n{}, {} ({})".format(
                    crayons.green(store.get("storeName")),
                    crayons.green(store.get("city")),
                    crayons.green(store.get("storeId")),
                )
            )
            
            
            store_name = store.get("storeName")
            for part_id, part in store.get("parts").items():
                title = (part.get("messageTypes", {}).get("regular", {}).get("storePickupProductTitle")
                or part.get("storePickupProductTitle")
                or part.get("productTitle")
                or "Unknown"
                )
                is_available = part.get("storePickEligible") or part.get("messageTypes", {}).get("regular", {}).get("storeSelectionEnabled")
                print(
                    " - {} {} ({})".format(
                    crayons.green("✔") if is_available else crayons.red("✖"),
                    crayons.green(title) if is_available else crayons.red(title),
                    crayons.green(part.get("partNumber")),
                    )
                )

                if part.get("messageTypes", {}).get("regular", {}).get("storeSelectionEnabled"):
                    stock_available = True
                    if part.get("partNumber") == "MG8H4QN/A" and store_name == "Liverpool":
                        email_items = {store_name: [title]}
                        send_email_alert()
                    else:
                        if store_name not in all_telegram_items:
                            all_telegram_items[store_name] = []
                        sku = part.get("partNumber")
                        web_link = f"https://www.apple.com/uk/shop/product/{sku}"
                        item_line = f'<a href="{web_link}">{title}</a>'
                        all_telegram_items[store_name].append(item_line)
                else:
                    print("No stock available for this item")    
                    
        if all_telegram_items:
            send_telegram_alert(all_telegram_items, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
                    

        if not not self.configuration.appointment_stores:
            self.get_store_availability()

    def find_devices(self):
        """Find the required devices based on the configuration."""
        # Store the information about the available devices for the family -
        # title, model, carrier.
        device_list = []
        # Downloading the list of products from the server for the current
        # device family.
        print("{}".format(crayons.blue("➜  Downloading Models List...")))
        product_locator_response = requests.get(
            self.PRODUCT_LOCATOR_URL.format(self.base_url, self.configuration.device_family)
        )

        if product_locator_response.status_code != 200 or product_locator_response.json() is None:
            return []

        try:
            product_list = (
                product_locator_response.json()
                .get("body")
                .get("productLocatorOverlayData")
                .get("productLocatorMeta")
                .get("products")
            )
            # Take out the product list and extract only the useful
            # information.
            for product in product_list:
                model = product.get("partNumber")
                carrier = product.get("carrierModel")
                # Only add the requested models and requested carriers (device
                # models are partially matched)
                if (
                    any(item in model for item in self.configuration.selected_device_models)
                    or len(self.configuration.selected_device_models) == 0
                ) and (
                    carrier in self.configuration.selected_carriers or len(self.configuration.selected_carriers) == 0
                ):
                    device_list.append({"title": product.get("productTitle"), "model": model, "carrier": carrier})

        except BaseException:
            print("{}".format(crayons.red("✖  Failed to find the device family")))
            if self.configuration.selected_device_models is not None:
                print("{}".format(crayons.blue("➜  Looking for device models instead...")))
                for model in self.configuration.selected_device_models:
                    device_list.append({"model": model})
        return device_list

    def check_stores_for_device(self, device):
        """Find all stores that have the device requested available."""
        response = requests.get(
            self.PRODUCT_AVAILABILITY_URL.format(self.base_url, device.get("model"), self.configuration.zip_code)
        )

        try:
            data = response.json()
        except ValueError:
            print(f"✖ Failed to decode JSON for model {device.get('model')}. Response text:\n{response.text}")
            time.sleep(1)
            return

        store_list = data.get("body", {}).get("stores", [])
    
        # Go through all the stores in the list and extract useful information.
        # Group products by store (put the stock for this device in the store's
        # parts attribute)
        for store in store_list:
            current_store = self.stores_list_with_stock.get(store.get("storeNumber"))
            if current_store is None:
                current_store = {
                    "storeId": store.get("storeNumber"),
                    "storeName": store.get("storeName"),
                    "city": store.get("city"),
                    "sequence": store.get("storeListNumber"),
                    "parts": {},
                }
            new_parts = store.get("partsAvailability")
            old_parts = current_store.get("parts")
            old_parts.update(new_parts)
            current_store["parts"] = old_parts

            # If the store is in the list of user's preferred list, add it to the
            # list to check for stock.
            if (
                store.get("storeNumber") in self.configuration.selected_stores
                or len(self.configuration.selected_stores) == 0
            ):
                self.stores_list_with_stock[store.get("storeNumber")] = current_store

    def get_store_availability(self):
        """Get a list of all the stores to check appointment availability."""
        print("{}".format(crayons.blue("➜  Downloading store appointment availability...\n")))
        store_availability_list = requests.get(
            self.STORE_APPOINTMENT_AVAILABILITY_URL.format(
                datetime.now().strftime("%Y-%m-%d"), datetime.utcnow().strftime("%H")
            )
        )
        slots_found = False
        for store in store_availability_list.json():
            if store.get("storeNumber") in self.configuration.appointment_stores:
                if store.get("appointmentsAvailable") is True:
                    print(
                        " - Appointment Slot Available: {} {} ({})".format(
                            crayons.green("✔"),
                            store.get("storeNumber"),
                            datetime.utcfromtimestamp(int(store.get("firstAvailableAppointment"))).strftime(
                                "%d-%m-%Y %H:%M:%S"
                            ),
                        )
                    )
                    slots_found = True
                else:
                    print(" - {} {}".format(crayons.red("✖"), store.get("storeNumber")))
        if slots_found is True:
            send_email_alert()
        print("{}".format(crayons.blue("\n✔  Done\n")))


def lambda_handler(event=None, context=None):
    SKU_MAP = {
        #test cases
        "iphone-16": "MYE93QN/A",
        # Regular 256 GB
        "256-mistblue": "MG6L4QN/A",
        "256-lavender": "MG6M4QN/A",
        "256-black": "MG6J4QN/A",
        "256-white": "MG6P4QN/A",
        "256-sage": "MG6N4QN/A",

        # Regular 512 GB
        "512-mistblue": "MG6T4QN/A",
        "512-lavender": "MG6U4QN/A",
        "512-black": "MG6P4QN/A",
        "512-white": "MG6K4QN/A",
        "512-sage": "MG6V4QN/A",

        # Pro 256 GB
        "256-silver-pro": "MG8G4QN/A",
        "256-blue-pro": "MG8J4QN/A",
        "256-orange-pro": "MG8H4QN/A",

        # Pro 256 GB
        "512-silver-pro": "MG8K4QN/A",
        "512-orange-pro": "MG8M4QN/A",
        "512-blue-pro": "MG8N4QN/A",

        # Pro 1 TB
        "1-silver-pro": "MG8P4QN/A",
        "1-orange-pro": "MG8Q4QN/A",
        "1-blue-pro": "MG8R4QN/A",

        # Pro Max 256
        "256-silver-max": "MFYM4QN/A",
        "256-orange-max": "MFYN4QN/A",
        "256-blue-max": "MFYP4QN/A",

        # Pro Max 512
        "512-silver-max": "MFYQ4QN/A",
        "512-orange-max": "MFYT4QN/A",
        "512-deepblue-max": "MFYU4QN/A",

        # Pro Max 1 TB
        "1-silver-max": "MFYV4QN/A",
        "1-orange-max": "MFYW4QN/A",
        "1-deepblue-max": "MFYX4QN/A",

        # Pro Max 2 TB
        "2-silver-max": "MFYY4QN/A",
        "2-orange-max": "MG004QN/A",
        "2-blue-max": "MG014QN/A",

        # Air 256 GB
        "256-blue-air": "MFYY4QN/A",
        "256-gold-air": "MG2N4QN/A",
        "256-white-air": "MG2M4QN/A",
        "256-black-air": "MG2L4QN/A",

        # Air 512 GB
        "512-blue-air": "MG2V4QN/A",
        "512-gold-air": "MG2N4QN/A",
        "512-white-air": "MG2T4QN/A",
        "512-black-air": "MG2Q4QN/A",

        # Air 1 TB
        "1-blue-air": "MG304QN/A",
        "1-gold-air": "MG2Y4QN/A",
        "1-white-air": "MG2X4QN/A",
        "1-black-air": "MG2W4QN/A"

    }


    try:
        response = requests.get("") ## Add a GitHub Gist link here for more dynamic iphone changes. MINE: "https://api.github.com/gists/3366400f9e25072e53bdbcd5b927701e"
        gist_data = response.json()
        models_file = gist_data["files"]["models.json"]["content"]
        models_config = json.loads(models_file)
        selected_model_labels = models_config["models"]
    except Exception as e:
        print(f"Error fetching models: {e}")
        selected_model_labels = [""]

    selected_models = [SKU_MAP.get(label, label) for label in selected_model_labels]

    
    store_checker = StoreChecker("config.json", selected_models)
    store_checker.refresh()

    return {"status": "done"}


