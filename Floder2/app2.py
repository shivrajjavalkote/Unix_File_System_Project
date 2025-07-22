from flask import Flask, request, jsonify, render_template, Blueprint

app = Flask(__name__)

# Initialize the hash queue with 7 boxes, each containing 3 free blocks
hash_queue = [[{"block_number": None, "purpose": "Free", "free": True} for _ in range(3)] for _ in range(7)]

# Blueprint for app2
app2_blueprint = Blueprint('app2', __name__, template_folder='templates')

@app2_blueprint.route('/page2')
def page2():
    """Render the second page."""
    return render_template('page2.html')

@app2_blueprint.route('/get_hash_queue', methods=['GET'])
def get_hash_queue():
    """Return the current state of the hash queue."""
    return jsonify(hash_queue)

@app2_blueprint.route('/add_block', methods=['POST'])
def add_block():
    """Add a block to the hash queue."""
    data = request.json
    block_number = data.get('block_number')
    purpose = data.get('purpose')

    if block_number is None or purpose is None:
        return jsonify({"error": "Missing block_number or purpose."}), 400

    if block_number < 0:
        return jsonify({"error": "Block number cannot be negative."}), 400

    # Check if the block already exists
    for box in hash_queue:
        for block in box:
            if block["block_number"] == block_number:
                if block["free"]:  # Block is free
                    block.update({"purpose": purpose, "free": False})
                    return jsonify({"message": f"Block {block_number} updated successfully."})
                else:  # Block is busy
                    return jsonify({"error": f"Block {block_number} is already busy."}), 400

    # Calculate the position using modulo division
    position = block_number % 7

    # Try to find a free block in the calculated box
    for block in hash_queue[position]:
        if block["free"]:
            block.update({"block_number": block_number, "purpose": purpose, "free": False})
            return jsonify({"message": f"Block {block_number} assigned successfully in Box {position}."})

    # Replace the first free block globally if none are available in the calculated box
    for box in hash_queue:
        for block in box:
            if block["free"]:
                block.update({"block_number": block_number, "purpose": purpose, "free": False})
                return jsonify({"message": f"Block {block_number} replaced a free block globally."})

    # If all blocks are busy, return an error
    return jsonify({"error": "All blocks are busy, cannot add a new block."}), 400

@app2_blueprint.route('/free_block', methods=['POST'])
def free_block():
    """Free a block and add it back to the Free List."""
    data = request.json
    block_number = data.get('block_number')

    if block_number is None:
        return jsonify({"error": "Missing block_number."}), 400

    if block_number < 0:
        return jsonify({"error": "Block number cannot be negative."}), 400

    for box in hash_queue:
        for block in box:
            if block["block_number"] == block_number and not block["free"]:
                block.update({"free": True, "purpose": "Free"})
                return jsonify({"message": f"Block {block_number} freed successfully."})

    return jsonify({"error": f"Block {block_number} is either already free or does not exist."}), 400

# Register the blueprint
app.register_blueprint(app2_blueprint, url_prefix='/app2')

if __name__ == '__main__':
    app.run(debug=True)
