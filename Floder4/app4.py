from flask import Flask, render_template, request, jsonify
import mysql.connector
from flask import Blueprint

app = Flask(__name__)

app4_blueprint = Blueprint('app4', __name__, template_folder='templates')

@app4_blueprint.route('/page4')
def page4():
    """Render the page."""
    return render_template('page4.html')

# Function to connect to the MySQL database
def connect_to_database():
    try:
        conn = mysql.connector.connect(
            host="localhost",  # Ensure this is correct
            user="python@123",
            password="pass123!",
            database="Project"
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# In-memory hash queue for simplicity (7 buckets)
hash_queue = [[{"block_number": None, "purpose": "Free", "free": True} for _ in range(3)] for _ in range(7)]

@app4_blueprint.route('/', methods=['GET', 'POST'])
def buffer_details():
    # Reset hash_queue for each search
    global hash_queue
    hash_queue = [[{"block_number": None, "purpose": "Free", "free": True} for _ in range(3)] for _ in range(7)]

    conn = connect_to_database()
    if conn is None:
        return "Failed to connect to the database."

    cursor = conn.cursor()
    search_components = []
    matched_block = None

    # Get user input as a file path
    search_input = request.form.get('search_name', '').strip()
    if search_input:
        search_components = [comp.strip() for comp in search_input.split('/')]
        last_component = search_components[-1]

        # Fetch the matching inode by filename
        cursor.execute("SELECT inode_id, filename FROM inode_table WHERE filename LIKE %s", (f"%{last_component}%",))
        matched = cursor.fetchone()

        if matched:
            inode_id, filename = matched
            hash_index = inode_id % 7
            matched_block = {"inode_id": inode_id, "filename": filename, "hash_index": hash_index}

            for block in hash_queue[hash_index]:
                if block['block_number'] is None:
                    block['block_number'] = inode_id
                    block['purpose'] = "Search Result"
                    block['free'] = False
                    break

    try:
        cursor.execute("SELECT inode_id, filename FROM inode_table")
        namei_data = cursor.fetchall()

        namei_columns = ["inode_id", "filename"]

        return render_template(
            'page4.html',
            namei_columns=namei_columns,
            namei_data=namei_data,
            search_components=search_components,
            matched_block=matched_block,
            hash_queue=hash_queue
        )
    except Exception as e:
        return f"Error fetching data: {e}"
    finally:
        cursor.close()
        conn.close()

@app4_blueprint.route('/add_block', methods=['POST'])
def add_block():
    data = request.json
    block_number = data.get('block_number')
    purpose = data.get('purpose', 'Unknown')

    if not block_number:
        return jsonify({"error": "Block number is required"}), 400

    for queue in hash_queue:
        for block in queue:
            if block['free']:
                block['block_number'] = block_number
                block['purpose'] = purpose
                block['free'] = False
                return jsonify({"message": f"Block {block_number} added to hash queue"}), 200

    for queue in hash_queue:
        for block in queue:
            if block['block_number'] is None:
                block['block_number'] = block_number
                block['purpose'] = purpose
                block['free'] = False
                return jsonify({"message": f"Block {block_number} added to hash queue (using null block)"}), 200

    return jsonify({"error": "No available block in the hash queue"}), 404

@app4_blueprint.route('/free_block', methods=['POST'])
def free_block():
    data = request.json
    block_number = data.get('block_number')

    if not block_number:
        return jsonify({"error": "Block number is required"}), 400

    for queue in hash_queue:
        for block in queue:
            if block['block_number'] == block_number:
                block['free'] = True
                return jsonify({"message": f"Block {block_number} freed"}), 200

    return jsonify({"error": "Block not found"}), 404

@app4_blueprint.route('/get_hash_queue', methods=['GET'])
def get_hash_queue():
    return jsonify(hash_queue)

app.register_blueprint(app4_blueprint, url_prefix='/app4')

if __name__ == '__main__':
    app.run(debug=True)
