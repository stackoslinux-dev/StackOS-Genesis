# StackOS Genesis Architecture

## Overview

StackOS Genesis is a modular Linux distribution built around a GNOME desktop environment.

The project separates the base operating system from StackOS-specific applications, helpers, services and recovery tooling.

## Base

Current base:

- Ubuntu 26.04 LTS
- GNOME 50
- Linux kernel 7.x
- APT package management
- systemd
- GRUB
- SquashFS-based installation image

Large generated system images are not stored in the Git repository.

## StackOS applications

StackOS provides its own desktop and system integration tools, including:

- installer
- firstboot
- software store
- driver manager
- updater
- package installer
- USB image writer
- welcome application
- bug reporting
- factory reset
- recovery helpers

## System integration

Privileged operations are separated into dedicated helpers and policy definitions instead of giving applications unrestricted administrative access.

StackOS also uses systemd services for background system functionality such as updates and recovery snapshots.

## Recovery model

The installed system is designed around dedicated recovery and backup functionality.

Recovery tooling includes:

- factory image creation
- system snapshots
- factory reset requests
- GRUB recovery integration
- recovery authentication handling

## Repository model

The Git repository stores source code, configuration and documentation.

Generated artifacts such as ISO images, SquashFS images and Debian packages are excluded from normal Git history.
