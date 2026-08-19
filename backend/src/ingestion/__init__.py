"""SaKgaZé automatic data ingestion layer.

Three independent collectors (sargassum, drift, marine-alerts) fetch from
authoritative public sources, normalize into the application's GeoJSON contract,
and write through the existing CRUD layer with idempotent deduplication.
"""
