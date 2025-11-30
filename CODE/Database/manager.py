import pyodbc

conn = pyodbc.connect(
    "Driver={SQL Server};"          # driver for MS SQL
    "Server=localhost\\SQLEXPRESS;" # instance name
    "Database=test;"         # your database name
    "Trusted_Connection=yes;"       # use Windows login
)

cursor = conn.cursor()

cursor.execute("SELECT AOA FROM aoa WHERE CL = 2.9")


for row in cursor:
    print(row)

conn.close()
