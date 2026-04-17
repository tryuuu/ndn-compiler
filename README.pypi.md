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

## Examples

Fetch data by NDN name and print it:

```ndn
let height = interest "/height/Mt.Fuji/"
print height
```

Fetch data and convert units with a local function:

```ndn
let height_m = interest "/height/Mt.Fuji/"
let height_ft = m_to_feet(height_m)
print height_ft
```

> These examples use locally registered data and run without NFD.
> When NFD and NLSR are running, `interest` first checks local data, and if not found, fetches it over the NDN network transparently.

## Requirements

- Python 3.10+
- [python-ndn](https://python-ndn.readthedocs.io/)

## NDN Network Requirements

To fetch data or execute functions over an actual NDN network, the following must be running on your machine:

- **NFD** (NDN Forwarding Daemon) — handles NDN packet forwarding
- **NLSR** (Named-data Link State Routing) — manages routing between NDN nodes

Without these, `interest` expressions will fall back to local data only.
