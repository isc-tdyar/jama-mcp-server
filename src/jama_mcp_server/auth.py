import os
import json
import logging
from typing import Tuple

# Define custom exceptions for clearer error handling
class CredentialsError(Exception):
    """Base class for credential-related errors."""
    pass

class MissingCredentialsError(CredentialsError):
    """Raised when required credentials are not found."""
    pass

class AWSParameterStoreError(CredentialsError):
    """Raised when there's an error interacting with AWS Parameter Store."""
    pass

class InvalidSecretFormatError(CredentialsError):
    """Raised when the secret fetched from Parameter Store has an invalid format."""
    pass

logger = logging.getLogger(__name__)

def get_bearer_token() -> str | None:
    """
    Retrieves JAMA bearer token from environment if available.

    Returns:
        str | None: Bearer token if found, None otherwise.
    """
    bearer_token = os.environ.get("JAMA_BEARER_TOKEN")
    if bearer_token:
        logger.info("Using JAMA_BEARER_TOKEN from environment variable.")
        return bearer_token
    return None

def get_jama_credentials() -> Tuple[str, str]:
    """
    Retrieves Jama OAuth credentials (client_id, client_secret).

    Resolution order:
    1. Environment variables (JAMA_CLIENT_ID, JAMA_CLIENT_SECRET)
    2. AWS Parameter Store (if JAMA_AWS_SECRET_PATH is set and direct variables are not)

    Environment Variables:
        JAMA_AWS_SECRET_PATH (str, optional): The name/path of the secret in AWS Parameter Store.
        JAMA_AWS_PROFILE (str, optional): The AWS profile name to use with boto3.
        JAMA_CLIENT_ID (str, optional): Jama OAuth Client ID (used if AWS path not set).
        JAMA_CLIENT_SECRET (str, optional): Jama OAuth Client Secret (used if AWS path not set).

    Returns:
        Tuple[str, str]: A tuple containing (client_id, client_secret).

    Raises:
        MissingCredentialsError: If neither AWS path nor direct env vars provide credentials.
        AWSParameterStoreError: If fetching from AWS fails (requires boto3).
        InvalidSecretFormatError: If the AWS secret format is incorrect.
        ImportError: If boto3 is required but not installed.
    """
    # 1. Check for direct environment variables first
    client_id = os.environ.get("JAMA_CLIENT_ID")
    client_secret = os.environ.get("JAMA_CLIENT_SECRET")

    if client_id and client_secret:
        logger.info("Using JAMA_CLIENT_ID and JAMA_CLIENT_SECRET from environment variables.")
        return client_id, client_secret
    else:
        logger.info("Direct JAMA_CLIENT_ID/SECRET not found or incomplete.")

    # 2. If direct variables not found, check for AWS Parameter Store path
    aws_secret_path = os.environ.get("JAMA_AWS_SECRET_PATH")
    if aws_secret_path:
        logger.info(f"Attempting to fetch Jama credentials from AWS Parameter Store path: {aws_secret_path}")
        try:
            import boto3
        except ImportError:
            logger.error("boto3 library is required to fetch credentials from AWS Parameter Store but is not installed.")
            # Raise the error here, as it's only needed if we reach this fallback path
            raise ImportError("boto3 is required for AWS Parameter Store integration. Please install it.")

        aws_profile = os.environ.get("JAMA_AWS_PROFILE")
        try:
            logger.info(f"Using AWS profile: {aws_profile if aws_profile else 'default'}")
            session = boto3.Session(profile_name=aws_profile)
            ssm_client = session.client('ssm')

            parameter = ssm_client.get_parameter(Name=aws_secret_path, WithDecryption=True)
            secret_string = parameter['Parameter']['Value']
            logger.info("Successfully retrieved secret from AWS Parameter Store.")

        except Exception:
            raise AWSParameterStoreError(f"Failed to retrieve secret from AWS Parameter Store path '{aws_secret_path}'")

        try:
            secret_data = json.loads(secret_string)
            aws_client_id = secret_data.get("client_id")
            aws_client_secret = secret_data.get("client_secret")

            if not aws_client_id or not aws_client_secret:
                raise InvalidSecretFormatError("AWS Parameter Store secret JSON must contain 'client_id' and 'client_secret' keys.")

            logger.info("Successfully parsed client_id and client_secret from AWS secret.")
            return aws_client_id, aws_client_secret

        except json.JSONDecodeError:
            raise InvalidSecretFormatError(f"Failed to parse JSON secret from AWS Parameter Store path '{aws_secret_path}'")
        except InvalidSecretFormatError: # Re-raise specific error
             raise
        except Exception: # Catch any other parsing/access errors
            raise InvalidSecretFormatError(f"Error processing secret data from AWS Parameter Store path '{aws_secret_path}'")

    # 3. If neither method worked, raise error
    logger.error("Missing required Jama OAuth credentials. Set JAMA_CLIENT_ID and JAMA_CLIENT_SECRET, or configure JAMA_AWS_SECRET_PATH.")
    raise MissingCredentialsError("Missing Jama OAuth credentials. Set environment variables (JAMA_CLIENT_ID, JAMA_CLIENT_SECRET) or configure AWS Parameter Store fallback (JAMA_AWS_SECRET_PATH).")