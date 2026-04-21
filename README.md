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

ローカル関数（`modify`）の動作確認:
```bash
make run S=examples/hello.ndn
# 出力例: local data from function
```

リモート関数（`remote_modify`）の動作確認:
```bash
make run S=examples/remote.ndn
# 出力例: local data from remote_modify
```

`remote_modify` は NDN Interest `/remote_modify/<arg>` を発行し、`remote_modify` コンテナが処理を行う。`make all` 実行時に自動で起動する。
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