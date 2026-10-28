"""Deployable processes: apps.api (HTTP) and apps.worker (queue consumer + scheduled jobs).
Both are stateless: everything that matters goes through the ports built in apps.wiring.
"""
