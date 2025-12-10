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
## Check Logs
```bash
make logs
```
## Stop Environment
```bash
make down
```