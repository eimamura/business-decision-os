# ADR: NVIDIA Container Toolkit for Docker GPU Access

Date: 2026-06-04

## Status

Accepted

## Context

GPU acceleration is required for running local LLM inference (Ollama) inside Docker containers,
as well as for any future ML workloads (embedding model fine-tuning, batch inference). Without
explicit GPU passthrough configuration, Docker containers cannot access the host's NVIDIA GPU.

The standard mechanism for exposing NVIDIA GPUs to Docker containers is the NVIDIA Container
Toolkit, which installs a container runtime hook (`nvidia-container-runtime`) that maps GPU
devices into the container namespace at launch time.

Reference: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html

## Decision

Install and use the NVIDIA Container Toolkit on developer and production host machines that have
NVIDIA GPUs. Configure Docker (or Docker Compose) to request GPU access where needed.

### Installation

Follow the official NVIDIA Container Toolkit installation guide for the host OS. The toolkit
installs:

- `nvidia-container-toolkit` — the core runtime hook
- `/etc/docker/daemon.json` entry for the `nvidia` runtime (or configured via `nvidia-ctk`)

### Docker Compose usage

Services that require GPU access declare a `deploy.resources.reservations.devices` block:

```yaml
services:
  ollama:
    image: ollama/ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### docker run usage

```bash
docker run --gpus all <image>
```

## Consequences

- Local LLM inference (Ollama) inside Docker can utilise the host GPU, reducing inference
  latency and enabling larger models.
- Developers without an NVIDIA GPU can still run all containers — GPU reservation is a
  request, not a requirement; containers fall back to CPU when no GPU is available.
- The toolkit must be installed on every GPU-equipped host (developer machines, CI runners,
  production nodes) before GPU-enabled containers will function.
- No application code changes are required; GPU access is purely an infrastructure concern.

## Reversibility

Low reversal cost. Remove the `deploy.resources.reservations.devices` block from
`docker-compose.yml` and uninstall the toolkit. No schema or code changes needed.
