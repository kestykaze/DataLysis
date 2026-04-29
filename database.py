import pymysql
import os

def get_connection():
    connection = pymysql.connect(
        host=os.environ.get('MYSQLHOSTE', 'localhost'),
        user=os.environ.get('MYSQLUSER', 'amazkest'),
        password=os.environ.get('MYSQLPASSWORD', '2Am2y4l2dcj2@!'),
        database=os.environ.get('MYSQLDATABASE', 'collecte_db'),
        port=int(os.environ.get('MYSQLPORT', 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection
