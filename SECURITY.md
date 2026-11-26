# Security policy

## Supported versions

ViewPrism is pre-release software. Only the latest release (currently the 0.1.x pre-releases) receives
fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them privately through GitHub:
**Security → Report a vulnerability** on this repository (private vulnerability reporting). Include the
ViewPrism version, Blender version, OS and steps to reproduce.

You can expect a first answer within about a week. Please give us reasonable time to fix the issue
before you disclose it.

## Scope

ViewPrism is a local Blender add-on. It makes no network connections, runs no external programs and only
writes files into the output folder you choose (manifest permission: `files`). Reports about writing
outside that folder, path handling, crashes caused by crafted scenes, or anything that changes a user's
scene or files unexpectedly are in scope. Vulnerabilities in Blender itself should be reported to the
Blender project.
