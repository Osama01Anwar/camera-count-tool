# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Core result types with a construction guard: a `ShutterReading` can only be
  created from a source id that resolves to a documented or hardware-verified
  registry entry.
- Fixed, centralized result messages and the mandatory unavailable disclaimer.
- Build-failing guards: no estimation vocabulary in shipped code, no networking
  imports or calls, no mock-device code outside `tests/`, no shell execution.
- Apache-2.0 licensing files and contributor documentation.

[Unreleased]: https://github.com/Osama01Anwar/camera-count-tool/commits/main
