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
        # Tunnel provider selection (new)
        config.TUNNEL_PROVIDER       = data.get("tunnel_provider",  config.TUNNEL_PROVIDER)       or config.TUNNEL_PROVIDER
        # Legacy/default to instatunnel if subdomain exists but no provider set
        if not config.TUNNEL_PROVIDER and data.get("tunnel_subdomain"):
            config.TUNNEL_PROVIDER = "instatunnel"
        # InstaTunnel settings
        config.INSTATUNNEL_API_KEY   = data.get("tunnel_api_key",   config.INSTATUNNEL_API_KEY)   or config.INSTATUNNEL_API_KEY
        config.INSTATUNNEL_SUBDOMAIN = data.get("tunnel_subdomain", config.INSTATUNNEL_SUBDOMAIN) or config.INSTATUNNEL_SUBDOMAIN
        # Cloudflare Tunnel settings (new)
        config.CLOUDFLARE_TUNNEL_TOKEN = data.get("cloudflare_token",   config.CLOUDFLARE_TUNNEL_TOKEN) or config.CLOUDFLARE_TUNNEL_TOKEN
        config.CLOUDFLARE_DOMAIN       = data.get("cloudflare_domain",  config.CLOUDFLARE_DOMAIN)       or config.CLOUDFLARE_DOMAIN
    except Exception:
        pass  # file doesn't exist yet — use blank defaults


def save_credentials(
    server_url,
    username,
    password,
    api_key=None,
    subdomain=None,
    tunnel_provider=None,
    cloudflare_token=None,
    cloudflare_domain=None,
):
    """Write credentials to disk and update config globals."""
    config.SERVER_URL            = server_url
    config.USERNAME              = username
    config.PASSWORD              = password
    
    # Tunnel provider
    if tunnel_provider:
        config.TUNNEL_PROVIDER = tunnel_provider
    
    # InstaTunnel
    if api_key is not None:
        config.INSTATUNNEL_API_KEY = api_key
    if subdomain is not None:
        config.INSTATUNNEL_SUBDOMAIN = subdomain
    
    # Cloudflare
    if cloudflare_token is not None:
        config.CLOUDFLARE_TUNNEL_TOKEN = cloudflare_token
    if cloudflare_domain is not None:
        config.CLOUDFLARE_DOMAIN = cloudflare_domain
    
    try:
        with open(config.CREDENTIALS_FILE, "w") as f:
            json.dump({
                "server_url":       server_url,
                "username":         username,
                "password":         password,
                "tunnel_provider":  config.TUNNEL_PROVIDER,
                "tunnel_api_key":   config.INSTATUNNEL_API_KEY,
                "tunnel_subdomain": config.INSTATUNNEL_SUBDOMAIN,
                "cloudflare_token": config.CLOUDFLARE_TUNNEL_TOKEN,
                "cloudflare_domain": config.CLOUDFLARE_DOMAIN,
            }, f, indent=2)
    except Exception as e:
        print(f"Could not save credentials: {e}")
