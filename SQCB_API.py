import mysql.connector
from flask import Flask, jsonify

app = Flask(__name__)

# การเชื่อมต่อกับ MySQL
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Kk@1234859",
    database="/sqcb"
)

# ฟังก์ชันในการดึงข้อมูล
@app.route('/get_data', methods=['GET'])
def get_data():
    cursor = mydb.cursor(dictionary=True)
    cursor.execute("SELECT * FROM your_table")
    rows = cursor.fetchall()
    return jsonify(rows)

if __name__ == '__main__':
    app.run(debug=True)
