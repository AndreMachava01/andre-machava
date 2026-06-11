import os
from dataclasses import dataclass


@dataclass
class CarrierEnv:
    base_url: str
    api_key: str | None = None
    api_secret: str | None = None


def get_env(prefix: str) -> CarrierEnv:
    return CarrierEnv(
        base_url=os.getenv(f'{prefix}_BASE_URL', ''),
        api_key=os.getenv(f'{prefix}_API_KEY'),
        api_secret=os.getenv(f'{prefix}_API_SECRET'),
    )


# Examples (to be filled in production environment):
# CORREIOS_BASE_URL, CORREIOS_API_KEY, CORREIOS_API_SECRET
# DHL_BASE_URL, DHL_API_KEY, DHL_API_SECRET
# LOCAL_CARRIER_BASE_URL, LOCAL_CARRIER_API_KEY, LOCAL_CARRIER_API_SECRET


