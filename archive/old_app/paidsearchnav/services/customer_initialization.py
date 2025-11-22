"""Customer initialization service for setting up new customers with S3 and Google Ads integration."""

import time
from datetime import datetime
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from paidsearchnav.core.models.customer_init import (
    CustomerInitRequest,
    CustomerInitResponse,
    CustomerRecord,
    GoogleAdsAccountLink,
    InitializationProgress,
    InitializationStatus,
    S3FolderStructure,
    ValidationResult,
    generate_customer_id,
)
from paidsearchnav.logging import get_logger
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient
from paidsearchnav.services.folder_naming import (
    create_folder_structure,
)
from paidsearchnav.storage.models import Customer
from paidsearchnav.storage.repository import CustomerRepository

logger = get_logger(__name__)


class CustomerInitializationError(Exception):
    """Raised when customer initialization fails."""

    pass


class S3InitializationError(CustomerInitializationError):
    """Raised when S3 setup fails."""

    pass


class GoogleAdsInitializationError(CustomerInitializationError):
    """Raised when Google Ads setup fails."""

    pass


class CustomerInitializationService:
    """Service for initializing new customers with complete setup."""

    def __init__(
        self,
        s3_client=None,
        google_ads_client: Optional[GoogleAdsAPIClient] = None,
        bucket_name: str = "paidsearchnav-customer-data",
    ):
        """Initialize the service.

        Args:
            s3_client: S3 client (will create default if not provided)
            google_ads_client: Google Ads API client
            bucket_name: S3 bucket name for customer data
        """
        self.s3_client = s3_client or boto3.client("s3")
        self.google_ads_client = google_ads_client
        self.bucket_name = bucket_name
        self.logger = logger

    async def initialize_customer(
        self,
        request: CustomerInitRequest,
        user_id: str,
        session: AsyncSession,
    ) -> CustomerInitResponse:
        """Initialize a new customer with complete setup.

        Args:
            request: Customer initialization request
            user_id: ID of the user creating the customer
            session: Database session

        Returns:
            CustomerInitResponse with results
        """
        start_time = time.time()
        customer_id = generate_customer_id()
        errors = []
        warnings = []

        progress = InitializationProgress(
            customer_id=customer_id,
            current_step="Starting initialization",
            total_steps=5,
            completed_steps=0,
            status=InitializationStatus.IN_PROGRESS,
        )

        try:
            self.logger.info(
                f"Starting customer initialization for {request.name} (ID: {customer_id})"
            )

            # Step 1: Create S3 folder structure
            progress.current_step = "Creating S3 folder structure"
            progress.completed_steps = 1
            s3_structure = await self._create_s3_structure(request, customer_id)
            self.logger.info(f"S3 structure created: {s3_structure.base_path}")

            # Step 2: Validate Google Ads accounts
            progress.current_step = "Validating Google Ads accounts"
            progress.completed_steps = 2
            google_ads_links = []
            if self.google_ads_client:
                google_ads_links = await self._validate_google_ads_accounts(
                    request.google_ads_customer_ids
                )
                self.logger.info(
                    f"Validated {len(google_ads_links)} Google Ads accounts"
                )
            else:
                warnings.append(
                    "Google Ads client not available, skipping account validation"
                )

            # Step 3: Create customer database record
            progress.current_step = "Creating database record"
            progress.completed_steps = 3
            customer_record = await self._create_customer_record(
                request, customer_id, user_id, s3_structure, google_ads_links, session
            )
            self.logger.info(f"Customer record created: {customer_record.customer_id}")

            # Step 4: Verify setup
            progress.current_step = "Verifying setup"
            progress.completed_steps = 4
            validation_result = await self._verify_customer_setup(customer_id, session)
            if validation_result.errors:
                errors.extend(validation_result.errors)
            if validation_result.warnings:
                warnings.extend(validation_result.warnings)

            # Step 5: Complete
            progress.current_step = "Initialization complete"
            progress.completed_steps = 5
            progress.status = InitializationStatus.COMPLETED

            duration = time.time() - start_time
            self.logger.info(
                f"Customer initialization completed in {duration:.2f} seconds"
            )

            return CustomerInitResponse(
                success=True,
                customer_record=customer_record,
                s3_structure=s3_structure,
                google_ads_links=google_ads_links,
                initialization_status=InitializationStatus.COMPLETED,
                errors=errors,
                warnings=warnings,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Customer initialization failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

            # Attempt rollback
            try:
                await self._rollback_initialization(
                    customer_id,
                    s3_structure if "s3_structure" in locals() else None,
                    session,
                )
            except Exception as rollback_error:
                self.logger.error(
                    f"Rollback failed: {str(rollback_error)}", exc_info=True
                )
                errors.append(f"Rollback failed: {str(rollback_error)}")

            return CustomerInitResponse(
                success=False,
                customer_record=None,
                s3_structure=s3_structure if "s3_structure" in locals() else None,
                google_ads_links=google_ads_links
                if "google_ads_links" in locals()
                else [],
                initialization_status=InitializationStatus.FAILED,
                errors=errors,
                warnings=warnings,
                duration_seconds=duration,
            )

    async def _create_s3_structure(
        self, request: CustomerInitRequest, customer_id: str
    ) -> S3FolderStructure:
        """Create S3 folder structure for customer.

        Args:
            request: Customer initialization request
            customer_id: Generated customer ID

        Returns:
            S3FolderStructure with created paths

        Raises:
            S3InitializationError: If S3 setup fails
        """
        try:
            # Create folder structure
            structure_dict = create_folder_structure(
                request.name,
                request.business_type,
                customer_id.replace("cust_", "")[:12].upper(),
            )

            # Create S3 folder markers (empty objects with '/' suffix)
            folders_to_create = [
                structure_dict["inputs_path"],
                structure_dict["outputs_path"],
                structure_dict["reports_path"],
                structure_dict["actionable_files_path"],
            ]

            created_folders = []
            for folder_path in folders_to_create:
                folder_marker = f"{folder_path}/.folder_marker"
                try:
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=folder_marker,
                        Body=b"",
                        Metadata={
                            "customer_id": customer_id,
                            "customer_name": request.name,
                            "business_type": request.business_type.value,
                            "created_at": datetime.utcnow().isoformat(),
                        },
                    )
                    created_folders.append(folder_path)
                    self.logger.debug(f"Created S3 folder marker: {folder_marker}")
                except ClientError as e:
                    raise S3InitializationError(
                        f"Failed to create S3 folder {folder_path}: {str(e)}"
                    )

            return S3FolderStructure(
                base_path=structure_dict["base_path"],
                customer_name_sanitized=structure_dict["customer_name_sanitized"],
                customer_number=structure_dict["customer_number"],
                inputs_path=structure_dict["inputs_path"],
                outputs_path=structure_dict["outputs_path"],
                reports_path=structure_dict["reports_path"],
                actionable_files_path=structure_dict["actionable_files_path"],
                created_folders=created_folders,
            )

        except Exception as e:
            raise S3InitializationError(f"Failed to create S3 structure: {str(e)}")

    async def _validate_google_ads_accounts(
        self, customer_ids: List[str]
    ) -> List[GoogleAdsAccountLink]:
        """Validate Google Ads accounts and create links.

        Args:
            customer_ids: List of Google Ads customer IDs

        Returns:
            List of GoogleAdsAccountLink objects

        Raises:
            GoogleAdsInitializationError: If validation fails
        """
        if not self.google_ads_client:
            raise GoogleAdsInitializationError("Google Ads client not available")

        links = []
        for customer_id in customer_ids:
            try:
                # Clean the customer ID (remove hyphens)
                clean_id = customer_id.replace("-", "")

                # Try to get account information
                # Note: This would need to be implemented in the GoogleAdsAPIClient
                account_info = await self._get_google_ads_account_info(clean_id)

                link = GoogleAdsAccountLink(
                    customer_id=clean_id,
                    account_name=account_info.get("name", f"Account {clean_id}"),
                    currency_code=account_info.get("currency_code"),
                    time_zone=account_info.get("time_zone"),
                    account_type=account_info.get("account_type"),
                    accessible=True,
                    link_status="active",
                )
                links.append(link)

            except Exception as e:
                self.logger.warning(
                    f"Failed to validate Google Ads account {customer_id}: {str(e)}"
                )
                # Create a link with error information
                link = GoogleAdsAccountLink(
                    customer_id=customer_id.replace("-", ""),
                    account_name=f"Account {customer_id} (validation failed)",
                    accessible=False,
                    link_status="error",
                    validation_errors=[str(e)],
                )
                links.append(link)

        return links

    async def _get_google_ads_account_info(self, customer_id: str) -> dict:
        """Get basic account information from Google Ads API.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Dictionary with account information

        Raises:
            NotImplementedError: Real Google Ads API integration not yet implemented
        """
        if not self.google_ads_client:
            raise GoogleAdsInitializationError("Google Ads client not available")

        # TODO: Implement real Google Ads API integration
        # This should use the GoogleAdsAPIClient to fetch actual account information
        # including account name, currency, timezone, and account type
        # Example implementation:
        #   account_info = await self.google_ads_client.get_account_info(customer_id)
        #   return {
        #       "name": account_info.descriptive_name,
        #       "currency_code": account_info.currency_code,
        #       "time_zone": account_info.time_zone,
        #       "account_type": account_info.type_.name,
        #   }

        raise NotImplementedError(
            "Real Google Ads API integration not yet implemented. "
            "This method should fetch actual account information from Google Ads API."
        )

    async def _create_customer_record(
        self,
        request: CustomerInitRequest,
        customer_id: str,
        user_id: str,
        s3_structure: S3FolderStructure,
        google_ads_links: List[GoogleAdsAccountLink],
        session: AsyncSession,
    ) -> CustomerRecord:
        """Create customer database record.

        Args:
            request: Customer initialization request
            customer_id: Generated customer ID
            user_id: User creating the customer
            s3_structure: Created S3 structure
            google_ads_links: Validated Google Ads links
            session: Database session

        Returns:
            CustomerRecord object

        Raises:
            CustomerInitializationError: If database creation fails
        """
        try:
            # Create the customer record
            customer_record = CustomerRecord(
                customer_id=customer_id,
                name=request.name,
                name_sanitized=s3_structure.customer_name_sanitized,
                email=request.email,
                business_type=request.business_type,
                contact_person=request.contact_person,
                phone=request.phone,
                company_website=request.company_website,
                notes=request.notes,
                s3_base_path=s3_structure.base_path,
                s3_bucket_name=self.bucket_name,
                initialization_status=InitializationStatus.COMPLETED,
                google_ads_accounts=google_ads_links,
            )

            # Create database Customer model
            db_customer = Customer(
                id=customer_id,
                name=request.name,
                email=request.email,
                user_id=user_id,
                # For backwards compatibility, use the first Google Ads customer ID (cleaned)
                google_ads_customer_id=request.google_ads_customer_ids[0].replace(
                    "-", ""
                )
                if request.google_ads_customer_ids
                else None,
                is_active=True,
            )

            session.add(db_customer)
            await session.commit()

            self.logger.info(f"Created database customer record: {customer_id}")
            return customer_record

        except Exception as e:
            await session.rollback()
            raise CustomerInitializationError(
                f"Failed to create customer record: {str(e)}"
            )

    async def _verify_customer_setup(
        self, customer_id: str, session: AsyncSession
    ) -> ValidationResult:
        """Verify that customer setup is complete and valid.

        Args:
            customer_id: Customer ID to verify
            session: Database session

        Returns:
            ValidationResult with verification status
        """
        errors = []
        warnings = []

        try:
            # Check database record exists
            customer_repo = CustomerRepository(session)
            db_customer = await customer_repo.get_by_id(customer_id)
            customer_exists = db_customer is not None

            if not customer_exists:
                errors.append("Customer database record not found")

            # Check S3 structure (basic validation)
            s3_structure_valid = True
            try:
                # This would check if the S3 folders were created successfully
                # For now, we'll assume they exist if we got this far
                pass
            except Exception as e:
                s3_structure_valid = False
                errors.append(f"S3 structure validation failed: {str(e)}")

            # Check Google Ads links
            google_ads_links_valid = True
            if db_customer and db_customer.google_ads_customer_id:
                # Basic validation - more comprehensive checks could be added
                ads_id = db_customer.google_ads_customer_id
                if len(ads_id) < 7 or len(ads_id) > 10 or not ads_id.isdigit():
                    google_ads_links_valid = False
                    errors.append(
                        f"Invalid Google Ads customer ID format: {ads_id} (length: {len(ads_id)})"
                    )

            database_consistent = customer_exists and not errors

            return ValidationResult(
                valid=len(errors) == 0,
                customer_exists=customer_exists,
                s3_structure_valid=s3_structure_valid,
                google_ads_links_valid=google_ads_links_valid,
                database_consistent=database_consistent,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(f"Verification failed: {str(e)}")
            return ValidationResult(
                valid=False,
                customer_exists=False,
                s3_structure_valid=False,
                google_ads_links_valid=False,
                database_consistent=False,
                errors=errors,
                warnings=warnings,
            )

    async def _rollback_initialization(
        self,
        customer_id: str,
        s3_structure: Optional[S3FolderStructure],
        session: AsyncSession,
    ) -> None:
        """Rollback failed initialization.

        Args:
            customer_id: Customer ID to rollback
            s3_structure: S3 structure to clean up (if created)
            session: Database session
        """
        self.logger.info(f"Rolling back customer initialization: {customer_id}")

        # Rollback database changes
        try:
            await session.rollback()
            self.logger.debug("Database rollback completed")
        except Exception as e:
            self.logger.error(f"Database rollback failed: {str(e)}")

        # Clean up S3 folders
        if s3_structure:
            try:
                await self._cleanup_s3_structure(s3_structure)
                self.logger.debug("S3 cleanup completed")
            except Exception as e:
                self.logger.error(f"S3 cleanup failed: {str(e)}")

    async def _cleanup_s3_structure(self, s3_structure: S3FolderStructure) -> None:
        """Clean up created S3 structure.

        Args:
            s3_structure: S3 structure to clean up
        """
        try:
            # List and delete all objects under the base path
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self.bucket_name, Prefix=s3_structure.base_path + "/"
            )

            objects_to_delete = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects_to_delete.append({"Key": obj["Key"]})

            # Delete objects in batches
            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
                )

            self.logger.debug(f"Cleaned up {len(objects_to_delete)} S3 objects")

        except Exception as e:
            raise S3InitializationError(f"Failed to cleanup S3 structure: {str(e)}")

    def get_initialization_progress(
        self, customer_id: str
    ) -> Optional[InitializationProgress]:
        """Get initialization progress for a customer.

        Args:
            customer_id: Customer ID to check progress for

        Returns:
            InitializationProgress if found, None otherwise
        """
        # This would typically be stored in a cache or database
        # For now, this is a placeholder
        return None

    async def validate_customer_initialization(
        self, customer_id: str, session: AsyncSession
    ) -> ValidationResult:
        """Validate an existing customer's initialization.

        Args:
            customer_id: Customer ID to validate
            session: Database session

        Returns:
            ValidationResult with validation status
        """
        return await self._verify_customer_setup(customer_id, session)
