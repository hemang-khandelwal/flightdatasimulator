import pyodbc


CONNECTION_STRING = (
    "Driver={SQL Server};"
    "Server=localhost\\SQLEXPRESS;"
    "Database=Flight Simulator;"
    "Trusted_Connection=yes;"
)


def get_connection():
    return pyodbc.connect(CONNECTION_STRING)
