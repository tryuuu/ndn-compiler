# Description
A minimal domain-specific language (DSL) interpreter for NDN-less syntax.  
Currently supports several simple operations.
# Setup
## Start Environment (Docker)
Build and start NFD and Producer containers.
```bash
make all
```
## Run examples
Run the consumer in a container.
```bash
make run
```

Run a local function (`modify`):
```bash
make run S=examples/hello.ndn
# example output: local data from function
```

Run a remote function (`remote_modify`):
```bash
make run S=examples/remote.ndn
# example output: local data from remote_modify
```

`remote_modify` sends an NDN Interest `/remote_modify/<arg>` and the seed server handles the execution. It is automatically started when running `make all`.
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

## Register a function

Run `setup_seed.py` to register a `.ndn` function to the seed server.

```bash
python3 setup_seed.py
# example output: [setup] created: /remote_modify
```

After registration, sending an Interest to `/remote_modify/(<arg>)` executes the `.ndn` code.

## content_type

| value | behavior |
|---|---|
| `ndn` | executes `.ndn` code on each Interest and returns the result |
| `static` | returns the `content` string as-is |