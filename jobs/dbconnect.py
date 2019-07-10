import MySQLdb #run 'pip install mysqlclient' to add package

def connection():
    conn = MySQLdb.connect(host='localhost',
                           user = 'root',
                           passwd = 'ryan1111',
                           db = 'arianb$fl')
    c = conn.cursor()

    return c, conn