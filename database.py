import pymysql 

def get_connection():
    connection = pymysql.connect(
        host='localhost',
        user='amazkest',
        password='2Am2y4l2dcj2@!',
        database='collecte_db',
        cursorclass=pymysql.cursors.DictCursor  #cette ligne permet d'avoir des resultats sous fome de dictionnaire facile a manipuler 
    )
    return connection