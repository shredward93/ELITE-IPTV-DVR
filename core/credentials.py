import json
import config


def load_credentials():
    """Read credentials.json and update config globals."""
    try:
        with open(config.CREDENTIALS_FILE) as f:
            data = json.load(f)
        config.SERVER_URL            = data.get("server_url",       config.SERVER_URL)            or config.SERVER_URL
        config.USERNAME              = data.get("username",         config.USERNAME)              or config.USERNAME
        config.PASSWORD              = data.get("password",         config.PASSWORD)              or config.PASSWORD
        config.INSTATUNNEL_API_KEY   = data.get("tunnel_api_key",   config.INSTATUNNEL_API_KEY)   or config.INSTATUNNEL_API_KEY
        config.INSTATUNNEL_SUBDOMAIN = data.get("tunnel_subdomain", config.INSTATUNNEL_SUBDOMAIN) or config.INSTATUNNEL_SUBDOMAIN
    except Exception:
        pass  # file doesn't exist yet — use blank defaults


def save_credentials(server_url, username, password, api_key, subdomain):
    """Write credentials to disk and update config globals."""
    config.SERVER_URL            = server_url
    config.USERNAME              = username
    config.PASSWORD              = password
    config.INSTATUNNEL_API_KEY   = api_key
    config.INSTATUNNEL_SUBDOMAIN = subdomain
    try:
        with open(config.CREDENTIALS_FILE, "w") as f:
            json.dump({
                "server_url":       server_url,
                "username":         username,
                "password":         password,
                "tunnel_api_key":   api_key,
                "tunnel_subdomain": subdomain,
            }, f, indent=2)
    except Exception as e:
        print(f"Could not save credentials: {e}")
