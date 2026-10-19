# Confluent preparation and connection

## Preparation model

For the first workshop, organizer-managed Confluent infrastructure is recommended. Precreate an assigned namespace per attendee: nine activity topics and one compacted factory-state topic. Provide explicit topic and consumer-group permissions. Record the allowed bootstrap endpoint and namespace in the Simulation Server enrollment configuration.

Each producer key needs describe/write access to its ten topics. Each local consumer key needs describe/read access and permission to use its assigned consumer-group prefix. Separate keys are preferred. A pilot may use one attendee-scoped pair with both permissions; document that such a key can publish forged events into that attendee's own view. It is not suitable for a trustworthy competitive leaderboard. Never distribute a shared cohort-wide key.

## Runtime connection

Use TLS certificate verification and SASL_SSL with the API-key PLAIN profile. Supply key and secret via configuration objects, not command-line arguments or browser JavaScript. Use explicit timeouts/retry limits. Cluster metadata success does not prove write or consumer permission; verify actual operations.

Do not treat a Kafka key as a Confluent management API key. Topic creation, ACL administration, cluster purchase and quotas are organizer tasks. If using attendee-owned clusters, approve the cluster and namespace before registration rather than allowing arbitrary endpoint requests from a hosted server.

## Connectivity and limits

Confirm Code Engine outbound access and attendee laptop Kafka access to the selected cluster. A private-only cluster requires an explicit network design; the default recommendation is an approved reachable cluster. Measure topic/key/client quotas against the cohort before class.

Use the topic settings in the shared contract, respecting managed-cluster replication. Rehearse key rotation, revoked-key backlog behavior and permission-denied diagnostics.

Reference: https://docs.confluent.io/cloud/current/client-apps/config-client.html
