# Hosted Agent Instance Shapes

Hosted agent compute sizes available for queue creation.

## Linux AMD64

| Shape | vCPU | Memory |
|-------|------|--------|
| `LINUX_AMD64_2X4` | 2 | 4 GB |
| `LINUX_AMD64_4X16` | 4 | 16 GB |
| `LINUX_AMD64_8X32` | 8 | 32 GB |
| `LINUX_AMD64_16X64` | 16 | 64 GB |

## Linux ARM64

| Shape | vCPU | Memory |
|-------|------|--------|
| `LINUX_ARM64_2X4` | 2 | 4 GB |
| `LINUX_ARM64_4X16` | 4 | 16 GB |
| `LINUX_ARM64_8X32` | 8 | 32 GB |
| `LINUX_ARM64_16X64` | 16 | 64 GB |

## macOS M2

| Shape | vCPU | Memory |
|-------|------|--------|
| `MACOS_M2_4X7` | 4 | 7 GB |
| `MACOS_M2_6X14` | 6 | 14 GB |
| `MACOS_M2_12X28` | 12 | 28 GB |

## macOS M4

| Shape | vCPU | Memory |
|-------|------|--------|
| `MACOS_M4_6X28` | 6 | 28 GB |
| `MACOS_M4_12X56` | 12 | 56 GB |

macOS queues accept additional settings: `macosVersion` (`SONOMA`, `SEQUOIA`, `TAHOE`) and `xcodeVersion`. Linux queues accept `agentImageRef` for custom Docker images.
