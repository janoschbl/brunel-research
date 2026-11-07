# read-only backend calls and the https action path

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://service.ivanto.de"
SRS = BASE + "/srs/api/v1"
ACTIONS = {
    "stopRequest": BASE + "/busaccess/stopRequest",
    "serviceRequest": BASE + "/busaccess/serviceRequest",
    "doorsignalRequest": BASE + "/busaccess/doorsignalRequest",
}
HEADERS = {"Accept": "application/json", "User-Agent": "brunel-bench/1"}


def _request(url: str, method: str = "GET", body: dict | None = None, timeout: float = 10.0) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(65537)
            text = raw[:65536].decode("utf-8", "replace")
            accepted = False
            try:
                accepted = bool(json.loads(text).get("status"))
            except Exception:
                pass
            return {
                "url": url,
                "code": response.status,
                "body": text,
                "truncated": len(raw) > 65536,
                "accepted": accepted,
            }
    except urllib.error.HTTPError as error:
        return {"url": url, "code": error.code, "body": error.read(65536).decode("utf-8", "replace"), "accepted": False}
    except Exception as error:
        return {"url": url, "error": f"{type(error).__name__}: {error}", "accepted": False}


def updates() -> dict:
    return _request(SRS + "/bluetooth/updates/")


def lookup(filename: str = "Padersprinter") -> dict:
    return _request(SRS + "/bluetooth/?" + urllib.parse.urlencode({"filename": filename}))


def action(name: str, address: str) -> dict:
    url = ACTIONS.get(name)
    if url is None:
        raise ValueError(f"unknown action {name}")
    return _request(url, method="POST", body={"btMac": address})


def vehicle_type(address: str) -> dict:
    return _request(SRS + "/bluetooth/vehicleType?" + urllib.parse.urlencode({"btMac": address}))


def ibis_service_info(address: str, api_key: str | None = None) -> dict:
    headers = dict(HEADERS)
    if api_key:
        headers["Authorization"] = api_key
    url = SRS + "/bluetooth/ibisServiceInfo?" + urllib.parse.urlencode({"btMac": address})
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {"url": url, "code": response.status, "body": response.read(65536).decode("utf-8", "replace")}
    except Exception as error:
        return {"url": url, "error": f"{type(error).__name__}: {error}"}
