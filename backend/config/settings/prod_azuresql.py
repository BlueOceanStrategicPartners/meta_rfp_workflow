"""Production settings: Azure SQL via mssql-django."""
from .base import *  # noqa: F403

DEBUG = False
DB_ENGINE_MODE = "azuresql"

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ["AZURE_SQL_DB_NAME"],  # noqa: F405
        "USER": os.environ["AZURE_SQL_USER"],
        "PASSWORD": os.environ["AZURE_SQL_PASSWORD"],
        "HOST": os.environ["AZURE_SQL_SERVER_HOST"],
        "PORT": "1433",
        "OPTIONS": {
            "driver": "ODBC Driver 18 for SQL Server",
            "extra_params": "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
        },
    }
}
