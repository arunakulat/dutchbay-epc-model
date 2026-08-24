- Replace the #1110 Codespaces sandbox's failing create-time SSH Feature with a
  repository-owned, digest-pinned Docker build that installs the required SSH
  transport from Debian-only sources, attests its package/configuration
  identity and runtime-generated host public keys, enforces the effective SSH
  policy, starts transport before the Codespaces post-create lifecycle, and
  distinguishes inherited base-image Feature metadata from an empty
  repository-configured Feature surface. Create the disposable environment
  without eager SSH status, enforce a monotonic five-minute transport watchdog,
  and carry its immutable name into the private-ingress control.
