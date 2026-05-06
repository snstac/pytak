# Docker

PyTAK publishes two container images to GHCR on tagged releases:

- `ghcr.io/snstac/pytak-deb:<tag>` installs PyTAK from the release `.deb` package.
- `ghcr.io/snstac/pytak-rpm:<tag>` installs PyTAK from the release `.rpm` package.

For stable release tags only, both images also publish `:latest`.

## Pull

```sh
docker pull ghcr.io/snstac/pytak-deb:<tag>
docker pull ghcr.io/snstac/pytak-rpm:<tag>
```

## Run

The image entrypoint is `pytak`, so arguments are passed directly to the CLI.

```sh
docker run --rm ghcr.io/snstac/pytak-deb:<tag> --help
```

### Send CoT from file

```sh
docker run --rm \
  -v "$PWD/events.xml:/data/events.xml:ro" \
  ghcr.io/snstac/pytak-deb:<tag> \
  --tx-file /data/events.xml tcp://takserver.example.com:8087
```

### Enroll with tak:// URL and connect

```sh
docker run --rm \
  -v "$PWD/pytak-certs:/home/pytak/.pytak/certs" \
  ghcr.io/snstac/pytak-deb:<tag> \
  "tak://com.atakmap.app/enroll?host=takserver.example.com&username=user&token=token"
```

## Configuration

Environment variables can be passed through as usual:

```sh
docker run --rm \
  -e DEBUG=1 \
  -e COT_URL=tcp://takserver.example.com:8087 \
  ghcr.io/snstac/pytak-rpm:<tag>
```

## Notes

- Containerized UDP multicast traffic may require host networking.
- For most deployments, use `tcp://`, `tls://`, `ws://`, `wss://`, or `tak://` instead of multicast.
- Persist `~/.pytak/certs` if you use `tak://` enrollment and want cert reuse between runs.
