"""Raw JSON → clean-zone Parquet, run as an AWS Glue (Spark) job.

Everything except `job.py` is pure Python with no Spark or AWS dependency, so
the transforms are unit-tested offline with pytest.
"""
