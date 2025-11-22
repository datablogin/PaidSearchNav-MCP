"""Tests for core base models."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import Field, ValidationError

from paidsearchnav.core.models.base import BaseModel, BasePSNModel, utc_now


class TestUtcNow:
    """Test the utc_now utility function."""

    def test_returns_datetime(self) -> None:
        """Test that utc_now returns a datetime object."""
        result = utc_now()
        assert isinstance(result, datetime)

    def test_timezone_aware(self) -> None:
        """Test that returned datetime is timezone aware."""
        result = utc_now()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_current_time(self) -> None:
        """Test that returned time is current."""
        before = datetime.now(timezone.utc)
        result = utc_now()
        after = datetime.now(timezone.utc)

        assert before <= result <= after


class TestBasePSNModel:
    """Test BasePSNModel base class."""

    def test_default_fields(self) -> None:
        """Test that default fields are created."""
        model = BasePSNModel()

        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_timestamps_are_utc(self) -> None:
        """Test that timestamps are in UTC."""
        model = BasePSNModel()

        assert model.created_at.tzinfo == timezone.utc
        assert model.updated_at.tzinfo == timezone.utc

    def test_timestamps_are_current(self) -> None:
        """Test that timestamps are set to current time."""
        before = datetime.now(timezone.utc)
        model = BasePSNModel()
        after = datetime.now(timezone.utc)

        assert before <= model.created_at <= after
        assert before <= model.updated_at <= after

    def test_custom_timestamps(self) -> None:
        """Test that custom timestamps can be provided."""
        custom_created = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        custom_updated = datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

        model = BasePSNModel(created_at=custom_created, updated_at=custom_updated)

        assert model.created_at == custom_created
        assert model.updated_at == custom_updated

    def test_model_config(self) -> None:
        """Test model configuration."""
        assert BasePSNModel.model_config["use_enum_values"] is True
        assert BasePSNModel.model_config["validate_assignment"] is True
        assert BasePSNModel.model_config["populate_by_name"] is True

    def test_datetime_serialization(self) -> None:
        """Test datetime field serialization."""
        model = BasePSNModel()

        # Test individual field serialization
        serializer = model.__class__.__pydantic_serializer__
        created_at_str = model.serialize_datetime(model.created_at)
        updated_at_str = model.serialize_datetime(model.updated_at)

        assert isinstance(created_at_str, str)
        assert isinstance(updated_at_str, str)
        assert created_at_str == model.created_at.isoformat()
        assert updated_at_str == model.updated_at.isoformat()

    def test_model_dump_json(self) -> None:
        """Test JSON serialization."""
        model = BasePSNModel()
        json_str = model.model_dump_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)

        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

        # Verify ISO format
        datetime.fromisoformat(data["created_at"])
        datetime.fromisoformat(data["updated_at"])

    def test_model_dump_json_with_mode_parameter(self) -> None:
        """Test that model_dump_json handles mode parameter gracefully."""
        model = BasePSNModel()

        # Should not raise error even with mode parameter
        json_str = model.model_dump_json(mode="json")
        assert isinstance(json_str, str)

        # Should work with other parameters
        json_str = model.model_dump_json(indent=2, exclude_unset=True)
        assert isinstance(json_str, str)

    def test_inheritance(self) -> None:
        """Test that custom models can inherit from BasePSNModel."""

        class CustomModel(BasePSNModel):
            name: str
            value: int = 42

        model = CustomModel(name="test")

        assert model.name == "test"
        assert model.value == 42
        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")

    def test_validation_on_assignment(self) -> None:
        """Test that validation occurs on field assignment."""

        class ValidatedModel(BasePSNModel):
            positive_number: int = Field(gt=0)

        model = ValidatedModel(positive_number=5)
        assert model.positive_number == 5

        # Should validate on assignment
        with pytest.raises(ValidationError):
            model.positive_number = -1

    def test_populate_by_name(self) -> None:
        """Test that models can be populated by field name."""

        class AliasModel(BasePSNModel):
            my_field: str = Field(alias="myField")

        # Should work with alias
        model1 = AliasModel(myField="value")
        assert model1.my_field == "value"

        # Should also work with field name
        model2 = AliasModel(my_field="value")
        assert model2.my_field == "value"


class TestBaseModel:
    """Test BaseModel (backward compatibility alias)."""

    def test_inheritance_from_base_psn_model(self) -> None:
        """Test that BaseModel inherits from BasePSNModel."""
        assert issubclass(BaseModel, BasePSNModel)

    def test_id_field(self) -> None:
        """Test that BaseModel has an optional id field."""
        # Without ID
        model1 = BaseModel()
        assert model1.id is None

        # With ID
        model2 = BaseModel(id="test-123")
        assert model2.id == "test-123"

    def test_all_fields_present(self) -> None:
        """Test that BaseModel has all expected fields."""
        model = BaseModel(id="123")

        assert hasattr(model, "id")
        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")

        assert model.id == "123"
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_json_serialization(self) -> None:
        """Test JSON serialization with id field."""
        model = BaseModel(id="test-456")
        json_str = model.model_dump_json()

        data = json.loads(json_str)
        assert data["id"] == "test-456"
        assert "created_at" in data
        assert "updated_at" in data

    def test_inheritance_pattern(self) -> None:
        """Test that custom models can inherit from BaseModel."""

        class UserModel(BaseModel):
            username: str
            email: str
            is_active: bool = True

        user = UserModel(id="user-123", username="testuser", email="test@example.com")

        assert user.id == "user-123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)


class TestDateTimeHandling:
    """Test datetime handling in base models."""

    def test_naive_datetime_handling(self) -> None:
        """Test handling of naive datetimes."""
        naive_dt = datetime(2023, 6, 1, 12, 0, 0)

        # BasePSNModel accepts naive datetimes but doesn't automatically convert them
        model = BasePSNModel(created_at=naive_dt)
        # The behavior depends on Pydantic version and configuration
        # Just verify it was accepted
        assert model.created_at.year == 2023
        assert model.created_at.month == 6
        assert model.created_at.day == 1

    def test_different_timezone_handling(self) -> None:
        """Test handling of datetimes with different timezones."""
        # Create datetime in different timezone
        try:
            import zoneinfo

            eastern = zoneinfo.ZoneInfo("US/Eastern")
        except ImportError:
            # Fallback for Python < 3.9 or systems without zoneinfo
            pytest.skip("zoneinfo not available on this system")

        eastern_dt = datetime(2023, 6, 1, 12, 0, 0, tzinfo=eastern)

        model = BasePSNModel(created_at=eastern_dt)

        # Should be stored with timezone info
        assert model.created_at.tzinfo is not None

    def test_iso_format_parsing(self) -> None:
        """Test parsing from ISO format strings."""
        iso_string = "2023-06-01T12:00:00+00:00"

        class TestModel(BasePSNModel):
            custom_date: datetime

        model = TestModel(
            custom_date=iso_string, created_at=iso_string, updated_at=iso_string
        )

        assert model.custom_date.year == 2023
        assert model.custom_date.month == 6
        assert model.custom_date.day == 1
        assert model.created_at == model.custom_date

    def test_serialization_consistency(self) -> None:
        """Test that serialization and deserialization are consistent."""
        original = BaseModel(id="test-789")

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        data = json.loads(json_str)
        restored = BaseModel(**data)

        assert restored.id == original.id
        assert restored.created_at.isoformat() == original.created_at.isoformat()
        assert restored.updated_at.isoformat() == original.updated_at.isoformat()


class TestComplexScenarios:
    """Test complex usage scenarios."""

    def test_nested_models(self) -> None:
        """Test base models in nested structures."""

        class Address(BaseModel):
            street: str
            city: str
            country: str = "US"

        class User(BaseModel):
            name: str
            address: Address

        address = Address(id="addr-1", street="123 Main St", city="Anytown")

        user = User(id="user-1", name="John Doe", address=address)

        assert user.address.street == "123 Main St"
        assert user.address.id == "addr-1"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.address.created_at, datetime)

    def test_list_of_models(self) -> None:
        """Test base models in lists."""

        class Item(BaseModel):
            name: str
            quantity: int

        class Order(BaseModel):
            items: list[Item]
            total: float = 0.0

        items = [
            Item(id="item-1", name="Widget", quantity=2),
            Item(id="item-2", name="Gadget", quantity=1),
        ]

        order = Order(id="order-1", items=items)

        assert len(order.items) == 2
        assert order.items[0].name == "Widget"
        assert all(isinstance(item.created_at, datetime) for item in order.items)

    def test_model_update_pattern(self) -> None:
        """Test updating model fields."""

        class UpdateableModel(BaseModel):
            status: str = "pending"
            counter: int = 0

        model = UpdateableModel(id="update-1")
        original_created = model.created_at
        original_updated = model.updated_at

        # Update fields
        model.status = "completed"
        model.counter = 5

        # Timestamps should not change automatically
        assert model.created_at == original_created
        assert model.updated_at == original_updated

        # Manual update pattern
        model.updated_at = utc_now()
        assert model.updated_at > original_updated

    def test_model_copy_pattern(self) -> None:
        """Test copying models."""

        class CopyableModel(BaseModel):
            name: str
            value: int

        original = CopyableModel(id="copy-1", name="Original", value=42)

        # Create a copy with modifications
        copy = original.model_copy(update={"name": "Copy", "id": "copy-2"})

        assert copy.id == "copy-2"
        assert copy.name == "Copy"
        assert copy.value == 42
        assert copy.created_at == original.created_at
        assert copy.updated_at == original.updated_at

    def test_field_exclusion(self) -> None:
        """Test excluding fields during serialization."""
        model = BaseModel(id="exclude-1")

        # Exclude timestamps
        data = model.model_dump(exclude={"created_at", "updated_at"})
        assert "created_at" not in data
        assert "updated_at" not in data
        assert data["id"] == "exclude-1"

        # Exclude in JSON
        json_str = model.model_dump_json(exclude={"created_at"})
        data = json.loads(json_str)
        assert "created_at" not in data
        assert "updated_at" in data
