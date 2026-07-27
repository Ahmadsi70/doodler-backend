"""RunPod client — cloud GPU execution for the animation pipeline.

Provides:
  - RunPodClient: check endpoints, submit sync/async jobs, create pods
  - run_animation_on_runpod(): full pipeline via RunPod serverless endpoint
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import requests

_API_BASE = "https://api.runpod.ai/v2"


class RunPodError(Exception):
    """RunPod API error."""


class RunPodClient:
    """Client for RunPod serverless GPU inference.

    Usage:
        client = RunPodClient()
        if client.health_check():
            result = client.run_sync({"prompt": "..."}, timeout=300)
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_id: str | None = None,
        timeout: int = 30,
    ):
        from dotenv import load_dotenv
        load_dotenv()

        self.api_key = api_key or os.getenv("RUNPOD_API_KEY", "")
        self.endpoint_id = endpoint_id or os.getenv("RUNPOD_ENDPOINT_ID", "")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ── Endpoint management ────────────────────────────────────────────

    def health_check(self) -> bool:
        """Check if the configured endpoint exists and is healthy."""
        if not self.endpoint_id:
            return False
        try:
            r = self._session.get(
                f"{_API_BASE}/{self.endpoint_id}/health",
                timeout=self.timeout,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_endpoints(self) -> list[dict[str, Any]]:
        """List all serverless endpoints (RunPod dashboard API)."""
        r = self._session.get(
            f"{_API_BASE}/endpoints",
            timeout=self.timeout,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("endpoints", [])

    def create_endpoint(
        self,
        name: str,
        template_id: str = "sd-fast",
        gpu_type: str = "NVIDIA GeForce RTX 4090",
        gpu_count: int = 1,
        idle_timeout: int = 5,
        max_workers: int = 1,
        container_disk_in_gb: int = 20,
    ) -> dict[str, Any]:
        """Create a new serverless endpoint."""
        payload = {
            "name": name,
            "templateId": template_id,
            "gpuTypeIds": [gpu_type],
            "gpuCount": gpu_count,
            "idleTimeout": idle_timeout,
            "maxWorkers": max_workers,
            "containerDiskInGb": container_disk_in_gb,
        }
        r = self._session.post(
            f"{_API_BASE}/endpoints",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        self.endpoint_id = data.get("id", "")
        return data

    # ── Job submission ─────────────────────────────────────────────────

    def run_sync(
        self,
        input_data: dict[str, Any],
        timeout: int = 600,
        poll_interval: float = 2.0,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Submit a synchronous job (blocking)."""
        if not self.endpoint_id:
            raise RunPodError("No endpoint configured")

        r = self._session.post(
            f"{_API_BASE}/{self.endpoint_id}/runsync",
            json={"input": input_data},
            timeout=timeout,
        )

        if r.status_code == 404:
            raise RunPodError(
                f"Endpoint '{self.endpoint_id}' not found. "
                "Create it first or check RUNPOD_ENDPOINT_ID"
            )
        if r.status_code == 400:
            raise RunPodError(f"Bad request: {r.text[:300]}")
        if r.status_code == 500:
            raise RunPodError(f"Endpoint error: {r.text[:300]}")
        r.raise_for_status()
        return r.json()

    def run_async(
        self,
        input_data: dict[str, Any],
        timeout: int = 30,
    ) -> str:
        """Submit an async job, return job ID."""
        if not self.endpoint_id:
            raise RunPodError("No endpoint configured")

        r = self._session.post(
            f"{_API_BASE}/{self.endpoint_id}/run",
            json={"input": input_data},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["id"]

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Check status of an async job."""
        r = self._session.get(
            f"{_API_BASE}/{self.endpoint_id}/status/{job_id}",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def wait_for_job(
        self,
        job_id: str,
        timeout: int = 600,
        poll_interval: float = 5.0,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Poll until an async job completes."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_job_status(job_id)
            s = status.get("status", "")
            if on_status:
                on_status(s)
            if s == "COMPLETED":
                return status.get("output", {})
            if s in ("FAILED", "CANCELLED"):
                raise RunPodError(
                    f"Job {job_id} {s}: {status.get('error', '')}"
                )
            time.sleep(poll_interval)
        raise RunPodError(f"Job {job_id} timed out after {timeout}s")

    # ── Pod management ─────────────────────────────────────────────────

    def create_pod(
        self,
        name: str,
        image: str = "runpod/pytorch:2.1.0-cuda12.1.1-cudnn8-runtime",
        gpu_type: str = "NVIDIA GeForce RTX 4090",
        gpu_count: int = 1,
        container_disk: int = 20,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a new GPU pod (for direct SSH access)."""
        payload = {
            "name": name,
            "imageName": image,
            "gpuTypeIds": [gpu_type],
            "gpuCount": gpu_count,
            "containerDiskSizeGb": container_disk,
            "env": env or {},
        }
        r = self._session.post(
            "https://api.runpod.ai/v2/pods",
            json=payload,
            timeout=self.timeout,
        )
        if r.status_code == 406:
            raise RunPodError(f"Cannot create pod: {r.text[:300]}")
        r.raise_for_status()
        return r.json()

    def terminate_pod(self, pod_id: str) -> None:
        """Terminate a pod."""
        self._session.delete(
            f"https://api.runpod.ai/v2/pods/{pod_id}",
            timeout=self.timeout,
        )

    # ── Animation pipeline helpers ─────────────────────────────────────

    def run_animation_pipeline(
        self,
        scene_board: dict[str, Any],
        model_config: dict[str, Any] | None = None,
        timeout: int = 1200,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run the full 8-layer animation pipeline on RunPod.

        Returns output dict with:
          - video (base64 encoded MP4)
          - manifest (frame manifest path)
          - report (compose report)
          - duration_sec, total_frames, fps
        """
        payload = {
            "scene_board": scene_board,
            "model_config": model_config or {},
        }
        return self.run_sync(payload, timeout=timeout, on_status=on_status)


# ── Module-level convenience ──────────────────────────────────────────────


def get_runpod_client() -> RunPodClient | None:
    """Return a RunPodClient if credentials are available, else None."""
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "").strip()
    if not api_key or not endpoint_id:
        return None
    client = RunPodClient(api_key=api_key, endpoint_id=endpoint_id)
    if client.health_check():
        return client
    return None


def get_available_gpu(required_vram_gb: int = 8) -> str | None:
    """Check locally for GPU availability (for local fallback)."""
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_mem / 1e9
            if vram >= required_vram_gb:
                return "local_cuda"
        return None
    except ImportError:
        return None
