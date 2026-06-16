from dataclasses import dataclass


@dataclass
class LicenseInfo:
    license_id: str
    email: str
    expiry_date: str  # YYYY-MM-DD or "never" for lifetime
    product: str
    is_valid: bool = False
    error_message: str = ""
    uses: int = 0  # Gumroad: number of times license has been verified
    purchase_date: str = ""  # Gumroad: sale_timestamp
    refunded: bool = False  # Gumroad: purchase was refunded
    disputed: bool = False  # Gumroad: purchase is disputed
