# IBM Cloud Code Engine Deployment Notes & Instructions

## Architecture
- Single application worker process (`min-scale=1`, `max-scale=1`).
- No rolling updates across stateful deployments; deploy with a brief maintenance window (stop old -> start new) to prevent split-epoch conflicts.
- Memory-only state: all factory instances, buffered events, and credentials reside in RAM.
- Health endpoints:
  - Liveness: `/health/live`
  - Readiness: `/health/ready`

## Code Engine Application Creation Example (CLI)
```bash
# 1. Create a secret/configmap for enrollment configuration
ibmcloud ce secret create --name hive-enrollment --from-file enrollment.json=./schemas/sample_enrollment.json

# 2. Deploy simulation application
ibmcloud ce app create \
  --name hive-simulation-server \
  --image <YOUR_REGISTRY>/hive-simulation-server:latest \
  --port 8080 \
  --min-scale 1 \
  --max-scale 1 \
  --cpu 1 \
  --memory 2G \
  --env PORT=8080 \
  --env MAX_FACTORIES=25 \
  --env FACTORY_TTL_SECONDS=21600 \
  --env FACTORY_BUFFER_LIMIT_EVENTS=10000 \
  --env FACTORY_BUFFER_LIMIT_BYTES=16777216 \
  --env SIM_TICK_MILLISECONDS=100 \
  --env SNAPSHOT_INTERVAL_MILLISECONDS=200 \
  --env ENROLLMENT_CONFIG_PATH=/config/enrollment.json \
  --mount-secret /config=hive-enrollment
```
