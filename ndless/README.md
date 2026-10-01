# Ndless CX II client

The calculator OS `5.2.0.771` is an officially supported CX II/CX II CAS
version in Ndless r2022. The client in `nsocket_ai.c` is intended to be built
with the Ndless SDK matching that release and the `nsocket` library.

## Calculator build

Install the Ndless SDK and make sure its toolchain commands (`nspire-gcc`,
`nspire-ld-bflt`, and `nspire-as`) are on `PATH`. Obtain the `nsocket` source
from <https://github.com/compujuckel/nsocket>, then build its calculator
library:

```bash
cd ns_client
make
make install
```

Compile this client with the same toolchain and link `libnsocket.a`:

```bash
nspire-gcc -Wall -W -marm -Os -I/path/to/nsocket/ns_client \
  -c nsocket_ai.c -o nsocket_ai.o
nspire-ld-bflt nsocket_ai.o /path/to/nsocket/ns_client/lib/libnsocket.a \
  -o nsocket_ai.elf
```

The resulting executable must be transferred to the calculator using an
Ndless-compatible file-transfer tool and run while Ndless is active.

Change `BRIDGE_HOST` and `BRIDGE_PORT` in `nsocket_ai.c` to the address and
port forwarded by the host transport.

## Host transport limitation

The upstream `nsocket/pc_host/main.c` is Windows-specific (`windows.h`,
Winsock, and TI's host NavNet DLL). It cannot be used directly on macOS. The
Python bridge's TCP service is ready on port `8766`, but a macOS NavNet/N-Link
transport still has to forward the calculator's USB channel to that port.
Do not run the calculator client until that host transport is available.
