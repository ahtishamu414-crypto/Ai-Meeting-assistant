import os
import requests


ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"


def get_env(name: str, default=None):
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    return value if value else default


def get_zoom_access_token():
    return get_env("ZOOM_ACCESS_TOKEN")


def refresh_zoom_access_token():
    """
    Refresh the Zoom OAuth access token.

    Returns:
        {
            "success": True,
            "access_token": "...",
            "refresh_token": "...",
            "expires_in": ...,
            "scope": "..."
        }
    """

    client_id = get_env("ZOOM_CLIENT_ID")
    client_secret = get_env("ZOOM_CLIENT_SECRET")
    refresh_token = get_env("ZOOM_REFRESH_TOKEN")

    if not client_id:
        return {
            "success": False,
            "error": "ZOOM_CLIENT_ID is not configured"
        }

    if not client_secret:
        return {
            "success": False,
            "error": "ZOOM_CLIENT_SECRET is not configured"
        }

    if not refresh_token:
        return {
            "success": False,
            "error": "ZOOM_REFRESH_TOKEN is not configured"
        }

    try:
        response = requests.post(
            ZOOM_OAUTH_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(
                client_id,
                client_secret
            ),
            timeout=30,
        )

    except requests.RequestException as e:
        return {
            "success": False,
            "error": "Unable to connect to Zoom",
            "details": str(e)
        }

    if response.status_code != 200:
        return {
            "success": False,
            "error": "Zoom token refresh failed",
            "status_code": response.status_code,
            "details": response.text
        }

    try:
        token_data = response.json()

    except Exception:
        return {
            "success": False,
            "error": "Zoom returned invalid token response"
        }

    access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")

    if not access_token:
        return {
            "success": False,
            "error": "Zoom did not return a new access token"
        }

    # Store tokens in current process
    os.environ["ZOOM_ACCESS_TOKEN"] = access_token

    if new_refresh_token:
        os.environ["ZOOM_REFRESH_TOKEN"] = new_refresh_token

    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": token_data.get("expires_in"),
        "scope": token_data.get("scope"),
    }


def zoom_api_request(
    method: str,
    url: str,
    **kwargs
):
    """
    Make an authenticated Zoom API request.

    Automatically refreshes the OAuth token if Zoom
    returns HTTP 401.
    """

    access_token = get_zoom_access_token()

    if not access_token:
        return None, {
            "error": "ZOOM_ACCESS_TOKEN is not configured"
        }

    headers = kwargs.pop("headers", {})

    headers["Authorization"] = (
        f"Bearer {access_token}"
    )

    headers["Content-Type"] = "application/json"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=60,
            **kwargs
        )

    except requests.RequestException as e:
        return None, {
            "error": "Unable to connect to Zoom",
            "details": str(e)
        }

    # Token expired
    if response.status_code == 401:

        refresh_result = (
            refresh_zoom_access_token()
        )

        if not refresh_result.get("success"):
            return None, {
                "error": (
                    "Zoom access token is invalid "
                    "and refresh failed"
                ),
                "details": refresh_result
            }

        new_access_token = (
            refresh_result["access_token"]
        )

        headers["Authorization"] = (
            f"Bearer {new_access_token}"
        )

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=60,
                **kwargs
            )

        except requests.RequestException as e:
            return None, {
                "error": (
                    "Unable to connect to Zoom "
                    "after token refresh"
                ),
                "details": str(e)
            }

    return response, None