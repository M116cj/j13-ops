"""ZANGETSU offline tools package.

Read-only / offline analytical helpers — never imported by runtime
modules (Arena pipeline, A2/A3 orchestrators, allocator, consumer).
Tools live here so that runtime modules cannot inadvertently couple
to analytical code paths.
"""
