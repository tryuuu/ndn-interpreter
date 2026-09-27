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

## Function return values

Use `return` to produce a function result. It stops execution of the current
script/function. `print` writes to stdout only and is never used as the result.
Without a `return`, the result is `None` (an empty response over the text NDN/gRPC interface).

Function (`average.ndn`):

```ndn
let avg = (arg0 + arg1) / 2
return avg
```

Caller:

```ndn
let result = average(10, 20)
print result
```

For CLI integrations, keep logs on stdout and write the return value separately:

```sh
ndnc run --result-file result.json average.ndn 10 20
```

`result.json` contains JSON `15`. `ndnc run` does not automatically print return
values. This also applies to cached function execution and `exec_in_context`.
Existing function scripts that used `print` as their return value must change to
`return`. Caller scripts that print results remain unchanged.

Release: the existing release-branch workflow increments the package version
from 0.0.6 to 0.0.7. Publish that version before building the function runtime and
invoker images pinned to 0.0.7; deploy both images before registering scripts using
`return`. Source-cache entries from before the migration may remain until their
TTL expires (300 seconds).
