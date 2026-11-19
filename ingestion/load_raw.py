import csv
import os
from io import StringIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

SOURCE_DIR = Path("data/source")

TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:"
        f"{os.environ['POSTGRES_PASSWORD']}@localhost:"
        f"{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)


def copy_insert(table, conn, keys, data_iter):
    """pandas to_sql method that bulk-loads rows with Postgres COPY instead of INSERT."""
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        buf = StringIO()
        csv.writer(buf).writerows(data_iter)
        buf.seek(0)
        cols = ", ".join(f'"{k}"' for k in keys)
        name = f"{table.schema}.{table.name}" if table.schema else table.name
        cur.copy_expert(f"COPY {name} ({cols}) FROM STDIN WITH CSV", buf)


def main():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw"))

    for filename, table in TABLES.items():
        df = pd.read_csv(SOURCE_DIR / filename, dtype=str)
        df["_ingested_at"] = pd.Timestamp.now(tz="UTC")
        df["_source_file"] = filename
        df.to_sql(
            table,
            engine,
            schema="raw",
            if_exists="replace",
            index=False,
            chunksize=50_000,
            method=copy_insert,
        )
        print(f"loaded raw.{table}: {len(df)} rows")


if __name__ == "__main__":
    main()