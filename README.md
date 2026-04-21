# Description
A minimal domain-specific language (DSL) interpreter for NDN-less syntax.  
Currently supports several simple operations.
# Setup
## Start Environment (Docker)
Build and start all containers (NFD, Producer, Seed).
```bash
make all
```
## Run examples
Run the consumer in a container.
```bash
make run
```

Fetch local data:
```bash
make run S=examples/local.ndn
# example output: data from local
```

Fetch remote data via NFD:
```bash
make run S=examples/remote.ndn
# example output: data from remote
```

Call a remote function (`remote_modify`) registered on the seed server:
```bash
make run S=examples/remote_modify.ndn
# example output: data from local modified
```

## Check Logs
```bash
make logs
```
## Stop Environment
```bash
make down
```

# Seed Server

The seed server listens on the `/seed` prefix and accepts NDN function registration and deletion.

## Register functions

```bash
python3 setup_seed_modify.py
# example output: created: /remote_modify

python3 setup_seed_feet.py
# example output: created: /m_to_feet
```

After registration, sending an Interest to `/remote_modify/(<arg>)` or `/m_to_feet/(<arg>)` executes the `.ndn` code on the seed server.

## content_type

| value | behavior |
|---|---|
| `ndn` | executes `.ndn` code on each Interest and returns the result |
| `static` | returns the `content` string as-is |
