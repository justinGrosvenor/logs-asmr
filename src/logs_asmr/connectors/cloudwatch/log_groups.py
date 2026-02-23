"""Paginated DescribeLogGroups / DescribeLogStreams with in-memory cache."""

from __future__ import annotations

import logging
import time

import boto3

from logs_asmr.connectors.cloudwatch.errors import CloudWatchError, translate_error
from logs_asmr.constants import LOG_GROUP_CACHE_TTL_SECONDS

logger = logging.getLogger("logs_asmr.connectors.cloudwatch.log_groups")


class LogGroupFetcher:
    """Fetches log groups and streams with caching."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list]] = {}

    def list_log_groups(
        self, profile: str, region: str
    ) -> list[tuple[str, str]]:
        """List all log groups for a profile/region. Returns (name, arn) tuples.

        Cached for 5 minutes.
        """
        cache_key = f"groups:{profile}:{region}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            session = boto3.Session(profile_name=profile, region_name=region)
            client = session.client("logs")
            groups: list[tuple[str, str]] = []

            paginator = client.get_paginator("describe_log_groups")
            for page in paginator.paginate():
                for group in page.get("logGroups", []):
                    name = group["logGroupName"]
                    arn = group.get("arn", "")
                    # AWS returns ARN with ":*" suffix — strip it for API calls
                    if arn.endswith(":*"):
                        arn = arn[:-2]
                    groups.append((name, arn))

            logger.info("Fetched %d log groups for %s/%s", len(groups), profile, region)
            self._set_cached(cache_key, groups)
            return groups
        except Exception as e:
            user_msg, detail = translate_error(e)
            logger.error("Failed to list log groups: %s", detail)
            raise CloudWatchError(user_msg, detail) from e

    def list_log_streams(
        self, profile: str, region: str, log_group: str, limit: int = 50
    ) -> list[str]:
        """List log streams for a log group. Cached for 5 minutes."""
        cache_key = f"streams:{profile}:{region}:{log_group}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            session = boto3.Session(profile_name=profile, region_name=region)
            client = session.client("logs")
            streams: list[str] = []

            paginator = client.get_paginator("describe_log_streams")
            for page in paginator.paginate(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                PaginationConfig={"MaxItems": limit},
            ):
                for stream in page.get("logStreams", []):
                    streams.append(stream["logStreamName"])

            logger.info(
                "Fetched %d streams for %s/%s/%s", len(streams), profile, region, log_group
            )
            self._set_cached(cache_key, streams)
            return streams
        except Exception as e:
            user_msg, detail = translate_error(e)
            logger.error("Failed to list log streams: %s", detail)
            raise CloudWatchError(user_msg, detail) from e

    def _get_cached(self, key: str) -> list | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.monotonic() - ts < LOG_GROUP_CACHE_TTL_SECONDS:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: list) -> None:
        self._cache[key] = (time.monotonic(), data)

    def invalidate(self) -> None:
        self._cache.clear()
