"""Translate boto3 CloudWatch exceptions to user-friendly messages."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import ConnectorError

logger = logging.getLogger("logs_asmr.connectors.cloudwatch.errors")


class CloudWatchError(ConnectorError):
    """Wraps a CloudWatch error with user-facing message and raw detail."""


def translate_error(exc: Exception) -> tuple[str, str]:
    """Translate a boto3 exception to (user_message, detail)."""
    detail = str(exc)
    class_name = type(exc).__name__

    if "ExpiredTokenException" in class_name or "ExpiredToken" in detail:
        return "AWS credentials have expired. Please refresh your credentials.", detail

    if "AccessDeniedException" in class_name or "AccessDenied" in detail:
        return "Access denied. Check your IAM permissions for CloudWatch Logs.", detail

    if "ResourceNotFoundException" in class_name or "ResourceNotFound" in detail:
        return "Log group or stream not found.", detail

    if "ThrottlingException" in class_name or "Throttling" in detail:
        return "Request throttled by AWS. Please wait a moment.", detail

    if "InvalidParameterException" in class_name:
        return "Invalid parameter in request.", detail

    if "LimitExceededException" in class_name:
        return "Live Tail session limit exceeded. Close other sessions first.", detail

    if "ServiceUnavailableException" in class_name:
        return "CloudWatch Logs service is temporarily unavailable.", detail

    if "NoCredentialsError" in class_name or "NoCredentials" in detail:
        return "No AWS credentials found. Configure AWS CLI or set environment variables.", detail

    if "EndpointConnectionError" in class_name or "Could not connect" in detail:
        return "Cannot connect to AWS. Check your network and region settings.", detail

    if "NoRegionError" in class_name or "must specify a region" in detail.lower():
        return "No AWS region configured. Set a default region in your AWS config.", detail

    return f"AWS error: {class_name}", detail
