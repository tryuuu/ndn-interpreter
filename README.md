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
