from flask import Flask, render_template, request, jsonify
from flask import Blueprint, render_template, redirect  # Import redirect


app = Flask(__name__)

app3_blueprint = Blueprint('app3', __name__, template_folder='templates')

@app3_blueprint.route('/page3')
def page3():
    """Render the second page."""
    return render_template('page3.html')

#app.register_blueprint(app3_blueprint, url_prefix='/app3')

BLOCK_SIZE = 1024  # Block size in bytes
POINTER_SIZE = 4  # Size of a pointer in bytes

NUM_DIRECT_BLOCKS = 10  # Number of direct blocks
SINGLE_INDIRECT_CAPACITY = (BLOCK_SIZE // POINTER_SIZE) * BLOCK_SIZE  # Capacity of single indirect
DOUBLE_INDIRECT_CAPACITY = (BLOCK_SIZE // POINTER_SIZE) * SINGLE_INDIRECT_CAPACITY
TRIPLE_INDIRECT_CAPACITY = (BLOCK_SIZE // POINTER_SIZE) * DOUBLE_INDIRECT_CAPACITY

def calculate_blocks(file_size):
    allocation = {
        "direct_blocks": [],
        "single_indirect": [],
        "double_indirect": [],
        "triple_indirect": []
    }

    # Calculate total number of data blocks required
    total_blocks = (file_size + BLOCK_SIZE - 1) // BLOCK_SIZE  # Round up

    # Allocate direct blocks
    for i in range(min(NUM_DIRECT_BLOCKS, total_blocks)):
        allocation["direct_blocks"].append(f"Direct Block {i}")
    total_blocks -= min(NUM_DIRECT_BLOCKS, total_blocks)

    # Allocate single indirect blocks
    if total_blocks > 0:
        single_blocks = min(SINGLE_INDIRECT_CAPACITY // BLOCK_SIZE, total_blocks)
        allocation["single_indirect"].extend([f"Block {i}" for i in range(single_blocks)])
        total_blocks -= single_blocks

    # Allocate double indirect blocks
    if total_blocks > 0:
        double_blocks = min(DOUBLE_INDIRECT_CAPACITY // BLOCK_SIZE, total_blocks)
        for i in range(double_blocks):
            double_index = i // (BLOCK_SIZE // POINTER_SIZE)  # Which double indirect block
            single_index = i % (BLOCK_SIZE // POINTER_SIZE)  # Which single indirect block within
            allocation["double_indirect"].append(
                f"Double Block {double_index}, Single Block {single_index}"
            )
        total_blocks -= double_blocks

    # Allocate triple indirect blocks
    if total_blocks > 0:
        triple_blocks = total_blocks
        for i in range(triple_blocks):
            level1 = i // ((BLOCK_SIZE // POINTER_SIZE) ** 2)
            level2 = (i // (BLOCK_SIZE // POINTER_SIZE)) % (BLOCK_SIZE // POINTER_SIZE)
            level3 = i % (BLOCK_SIZE // POINTER_SIZE)
            allocation["triple_indirect"].append(f"L1 {level1}, L2 {level2}, L3 {level3}")

    return allocation

@app3_blueprint.route('/')
def home():
    return render_template('index.html')

@app3_blueprint.route('/bmap', methods=['POST'])
def bmap():
    file_size = int(request.json.get('file_size', 0))
    blocks = calculate_blocks(file_size)
    return jsonify(blocks)

if __name__ == '__main__':
    app.run(debug=True)
