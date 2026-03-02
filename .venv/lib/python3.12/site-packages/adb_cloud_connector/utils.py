import json
import os
import time
from json.decoder import JSONDecodeError
from typing import Any, Dict, Optional

import requests
from requests.exceptions import HTTPError

Json = Dict[str, Any]
dir_path = os.path.dirname(os.path.realpath(__file__))


def get_temp_credentials(
    tutorialName: Optional[str] = None,
    credentialProvider: str = "https://tutorials.arangodb.cloud:8529/_db/_system/tutorialDB/tutorialDB",
) -> Json:
    creds_file = f"{dir_path}/data/creds.json"

    try:
        with open(creds_file) as file:
            cache: Json = json.load(file)
        verify_url = f"{cache['url']}/_db/{cache['dbName']}/_api/collection"
        response = requests.get(verify_url, auth=(cache["username"], cache["password"]))
        response.raise_for_status()

        print("Success: reusing cached credentials")
        return cache

    except (JSONDecodeError, HTTPError):
        print("Log: requesting new credentials...")
        url = credentialProvider
        body = {"tutorialName": tutorialName} if tutorialName else "{}"
        response = requests.post(url, data=json.dumps(body))
        response.raise_for_status()

        data: Json = response.json()
        data["url"] = f"https://{data['hostname']}:{str(data['port'])}"

        with open(creds_file, "w+") as outfile:
            json.dump(data, outfile)
            outfile.close()

        time.sleep(10)  # Give instance enough time to provision

        print("Succcess: new credentials acquired")
        return data
