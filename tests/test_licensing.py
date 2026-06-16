import pytest
from unittest.mock import patch, MagicMock
import requests
from domain.licensing.entities import LicenseInfo
from domain.ports.registry import DomainRegistry
from infrastructure.adapters.license_service import GumroadLicenseService


def test_license_info_entity():
    info = LicenseInfo(
        license_id="LIC-12345",
        email="test@example.com",
        expiry_date="2027-12-31",
        product="Synapse Desktop",
        is_valid=True,
        error_message="",
        uses=2,
        purchase_date="2026-06-16T10:00:00Z",
        refunded=False,
        disputed=False,
    )
    assert info.license_id == "LIC-12345"
    assert info.email == "test@example.com"
    assert info.expiry_date == "2027-12-31"
    assert info.product == "Synapse Desktop"
    assert info.is_valid is True
    assert info.error_message == ""
    assert info.uses == 2
    assert info.purchase_date == "2026-06-16T10:00:00Z"
    assert info.refunded is False
    assert info.disputed is False


def test_license_service_registry_not_registered():
    # Reset state to prevent test pollution
    original_service = DomainRegistry._license_service
    DomainRegistry._license_service = None
    try:
        with pytest.raises(AttributeError):
            DomainRegistry.license_service()
    finally:
        DomainRegistry._license_service = original_service


def test_app_settings_contains_license_key():
    from domain.config.app_settings import AppSettings

    settings = AppSettings()
    assert hasattr(settings, "license_key")
    assert settings.license_key == ""

    settings_dict = settings.to_dict()
    assert "license_key" in settings_dict

    loaded_settings = AppSettings.from_dict({"license_key": "A1B2C3D4"})
    assert loaded_settings.license_key == "A1B2C3D4"


def test_license_service_empty_key():
    service = GumroadLicenseService()
    info = service.verify_license_key("")
    assert info.is_valid is False
    assert "empty" in info.error_message.lower()


@patch("requests.post")
def test_license_service_valid_key(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "uses": 1,
        "purchase": {
            "email": "buyer@example.com",
            "product_name": "Synapse Desktop",
            "sale_timestamp": "2026-06-16T10:00:00Z",
            "refunded": False,
            "disputed": False,
        },
    }
    mock_post.return_value = mock_response

    service = GumroadLicenseService(product_id="test-prod-id")
    info = service.verify_license_key("A1B2C3D4")

    assert info.is_valid is True
    assert info.license_id == "A1B2C3D4"
    assert info.email == "buyer@example.com"
    assert info.product == "Synapse Desktop"
    assert info.uses == 1
    assert info.refunded is False
    assert info.disputed is False

    mock_post.assert_called_once_with(
        "https://api.gumroad.com/v2/licenses/verify",
        json={
            "product_id": "test-prod-id",
            "license_key": "A1B2C3D4",
            "increment_uses_count": True,
        },
        timeout=10,
    )


@patch("requests.post")
def test_license_service_invalid_key_404(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_post.return_value = mock_response

    service = GumroadLicenseService()
    info = service.verify_license_key("INVALID-KEY")
    assert info.is_valid is False
    assert "invalid" in info.error_message.lower()


@patch("requests.post")
def test_license_service_refunded_key(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "uses": 2,
        "purchase": {
            "email": "buyer@example.com",
            "product_name": "Synapse Desktop",
            "sale_timestamp": "2026-06-16T10:00:00Z",
            "refunded": True,
            "disputed": False,
        },
    }
    mock_post.return_value = mock_response

    service = GumroadLicenseService()
    info = service.verify_license_key("REFUNDED-KEY")
    assert info.is_valid is False
    assert info.refunded is True
    assert "refunded" in info.error_message.lower()


@patch("requests.post")
def test_license_service_disputed_key(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "uses": 1,
        "purchase": {
            "email": "buyer@example.com",
            "product_name": "Synapse Desktop",
            "sale_timestamp": "2026-06-16T10:00:00Z",
            "refunded": False,
            "disputed": True,
        },
    }
    mock_post.return_value = mock_response

    service = GumroadLicenseService()
    info = service.verify_license_key("DISPUTED-KEY")
    assert info.is_valid is False
    assert info.disputed is True
    assert "disputed" in info.error_message.lower()


@patch("requests.post")
def test_license_service_expired_subscription(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "uses": 1,
        "purchase": {
            "email": "buyer@example.com",
            "product_name": "Synapse Desktop",
            "sale_timestamp": "2026-06-16T10:00:00Z",
            "refunded": False,
            "disputed": False,
            "subscription_ended_at": "2026-06-15T10:00:00Z",
        },
    }
    mock_post.return_value = mock_response

    service = GumroadLicenseService()
    info = service.verify_license_key("EXPIRED-SUB-KEY")
    assert info.is_valid is False
    assert "expired" in info.error_message.lower()


@patch("requests.post")
def test_license_service_network_error(mock_post):
    mock_post.side_effect = requests.exceptions.RequestException("Connection timed out")

    service = GumroadLicenseService()
    info = service.verify_license_key("ANY-KEY")
    assert info.is_valid is False
    assert "network error" in info.error_message.lower()
