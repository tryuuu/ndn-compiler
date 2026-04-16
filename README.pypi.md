# ndnc

A DSL interpreter for transparent distributed execution over NDN (Named Data Networking).

Write code without thinking about where it runs — local or remote. The system handles it.

## Installation

```bash
pip install ndnc
```

## Usage

### Run a `.ndn` script

```bash
ndnc run path/to/script.ndn
```

### Run with arguments

```bash
ndnc run path/to/script.ndn arg0 arg1
```

### Start NDN server (producer)

```bash
ndnc serve
```

## Example

```ndn
let data = interest "nakazatolab/data"
let result = func modify(data)
print result
```

## Requirements

- Python 3.10+
- [python-ndn](https://python-ndn.readthedocs.io/)
