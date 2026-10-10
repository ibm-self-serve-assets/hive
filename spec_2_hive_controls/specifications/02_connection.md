# Connect and obtain a factory

## Initial experience

The connection screen asks for the Simulation Server URL, workshop access token, approved profile and producer key/secret, plus local consumer credentials when separate. Store secrets in the OS credential store where available, otherwise a private permission-restricted configuration file ignored by git. Do not use browser localStorage. Clear password fields after submission and never return saved secrets from the local API.

The local backend authenticates with the server and lists the owner's existing factory first. If one exists, reconnect to it rather than creating another. Otherwise POST /v1/factories with an idempotency key and the producer credentials; poll the returned operation with bounded backoff. The server validates the enrolled namespace and returns its exact topic names.

Show provisioning / connection failed / ready paused. On ready start the local consumer with the returned topic list and authorized consumer-group prefix. UI inventory remains awaiting_events until a valid factory.state record arrives. A successful control API response is not a Kafka observation.

## Credential roles

Producer credentials go to the hosted server through HTTPS. Consumer credentials remain in the local backend. The owner bearer token controls the factory API and is unrelated to Kafka authentication. Never send the owner token to Confluent or confuse it with an API key.

Use TLS certificate verification and SASL_SSL/PLAIN for Kafka API-key credentials. A successful metadata query alone does not prove the read/group ACL is correct; complete a real consumption test. Keep the assigned topic names from server responses, not a hand-typed prefix.

## Recovery

Keep factory_id, profile and topics in memory. On local app restart, authenticate and rediscover the current owned factory before starting a fresh replay consumer session. A disconnected local application reconnects without resetting the factory if the server epoch is unchanged. If the server restarted, ask for fresh registration and producer credentials; never resurrect an old factory from Kafka history. Use the connection-update endpoint to rotate producer credentials for the same assigned profile; rotate the local consumer independently. An expired factory requires organizer renewal/new enrollment under server policy, not silently recreating it with someone else's token.

Configuration names, sources and validation rules are defined in nn_setup.md. SIMULATION_SERVER_URL targets the control API; CONFLUENT_BOOTSTRAP_SERVERS and CONFLUENT_CONSUMER_API_KEY / CONFLUENT_CONSUMER_API_SECRET configure the separate Kafka consumer connection.
