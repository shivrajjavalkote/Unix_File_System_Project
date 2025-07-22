from flask import Flask, render_template, request
import mysql.connector
from mysql.connector import pooling
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import atexit
from flask import Blueprint, render_template, redirect  # Import redirect


app = Flask(__name__)

app5_blueprint = Blueprint('app5', __name__, template_folder='templates')
# Register the blueprint with the Flask app





@app5_blueprint.route('/page5')
def page5():
    """Render the second page."""
    return render_template('page5.html')
#app.register_blueprint(app5_blueprint, url_prefix='/app5')


# Set up logging
logging.basicConfig(level=logging.INFO)

# Database connection pool
pool_config = {
    "host": "localhost",
    "user": "root",
    "password": "Pri@2003",
    "database": "filesystem_simulator",
    "pool_name": "mypool",
    "pool_size": 5
}
connection_pool = None

try:
    connection_pool = pooling.MySQLConnectionPool(**pool_config)
except mysql.connector.Error as e:
    app.logger.error(f"Error initializing connection pool: {e}")




# Database connection function with connection pooling
def get_db_connection():
    if not connection_pool:
        raise Exception("Database connection pool not initialized")
    try:
        return connection_pool.get_connection()
    except mysql.connector.Error as e:
        app.logger.error(f"Database connection error: {e}")
        raise Exception("Database connection error. Please try again later.")




# Optimized query to fetch directory structure and files in one go
def get_directory_structure():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all root directories (parent_directory IS NULL)
    cursor.execute('''
        SELECT fd.parent_directory, fd.inode_id, fd.name, i.file_type
        FROM file_directory fd
        JOIN inode i ON fd.inode_id = i.inode_id
        WHERE fd.parent_directory IS NULL
    ''')
    root_directories = cursor.fetchall()

    # Function to recursively fetch subdirectories and files
    def get_subdirectories(parent_directory):
        cursor.execute('''
            SELECT fd.parent_directory, fd.inode_id, fd.name, i.file_type
            FROM file_directory fd
            JOIN inode i ON fd.inode_id = i.inode_id
            WHERE fd.parent_directory = %s
        ''', (parent_directory,))
        subdirectories = cursor.fetchall()
        result = []
        for subdirectory in subdirectories:
            result.append({
                'inode_id': subdirectory['inode_id'],
                'name': subdirectory['name'],
                'file_type': subdirectory['file_type'],
                'subdirectories': get_subdirectories(subdirectory['inode_id']),
                'files': get_files(subdirectory['inode_id'])
            })
        return result

    def get_files(directory_id):
        cursor.execute('''
            SELECT fd.parent_directory, fd.inode_id, fd.name, i.file_type
            FROM file_directory fd
            JOIN inode i ON fd.inode_id = i.inode_id
            WHERE fd.parent_directory = %s AND i.file_type = 'regular'
        ''', (directory_id,))
        files = cursor.fetchall()
        return [{'inode_id': file['inode_id'], 'name': file['name'], 'file_type': file['file_type']} for file in files]

    structure = []
    for root in root_directories:
        structure.append({
            'inode_id': root['inode_id'],
            'name': root['name'],
            'file_type': root['file_type'],
            'subdirectories': get_subdirectories(root['inode_id']),
            'files': get_files(root['inode_id'])
        })

    cursor.close()
    connection.close()

    return structure





# Fetch block data from the database
def get_block_data_from_db(block_number):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
        SELECT block_data 
        FROM file_data_blocks 
        WHERE block_number = %s
        """, (block_number,))
        block_data = cursor.fetchone()
        cursor.close()
        connection.close()
        return block_data[0] if block_data else None
    except mysql.connector.Error as e:
        app.logger.error(f"Error fetching data: {e}")
        return None

# Batch fetching inode data
def get_inode_data_from_db_batch(inode_ids):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = f"SELECT * FROM inode WHERE inode_id IN ({','.join(map(str, inode_ids))})"
        cursor.execute(query)
        inode_data_list = cursor.fetchall()
        cursor.close()
        connection.close()
        return {data['inode_id']: data for data in inode_data_list}
    except mysql.connector.Error as e:
        app.logger.error(f"Error fetching inode data in batch: {e}")
        raise Exception("Error fetching inode data. Please try again later.")
inode_cache = {}

class Inode:
    def __new__(cls, inode_number):
        if inode_number in inode_cache:
            return inode_cache[inode_number]
        instance = super(Inode, cls).__new__(cls)
        inode_cache[inode_number] = instance
        return instance

    def __init__(self, inode_number):
        if hasattr(self, 'initialized'):
            return
        self.inode_id = inode_number
        self.file_name = ""
        self.file_type = ""
        self.size = 1024
        self.permissions = ""
        self.owner = None
        self.group = None
        self.created = None
        self.last_modified = None
        self.last_accessed = None
        self.initialized = True

    def populate_from_db(self, inode_data):
        # Safely populate attributes from database result
        self.file_name = inode_data.get("filename", "")
        self.file_type = inode_data.get("file_type", "")
        self.size = inode_data.get("size", 1024)
        self.permissions = inode_data.get("permissions", "")
        self.owner = inode_data.get("owner", None)
        self.group = inode_data.get("group", None)
        self.created = inode_data.get("created", None)
        self.last_modified = inode_data.get("last_modified", None)
        self.last_accessed = inode_data.get("last_accessed", None)

    def to_dict(self):
        # Return the inode attributes as a dictionary
        return {
            "inode_id": self.inode_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "size": self.size,
            "permissions": self.permissions,
            "owner": self.owner,
            "group": self.group,
            "created": self.created,
            "last_modified": self.last_modified,
            "last_accessed": self.last_accessed,
        }

   
class DiskBlock:
    def __init__(self, block_number, block_type, content=None, start_inode_id=0, disk_metadata=None):
        self.block_number = block_number
        self.block_type = block_type
        self.content = content or self._fetch_block_data_from_db()
        self.inodes = []
        self.start_inode_id = start_inode_id
        self.disk_metadata = disk_metadata
        self.status = "free" if self.content == "" else "used"

        if self.block_type == "inode":
            self._populate_inodes()
        elif self.block_type == "super" and self.disk_metadata:
            self._populate_superblock()

    def _populate_superblock(self):
        if self.disk_metadata:
            self.content = f"Block Size: {self.disk_metadata['block_size']} KB\n" \
                           f"Total Blocks: {self.disk_metadata['num_blocks']}\n" \
                           f"Data Blocks: {self.disk_metadata['data_block_count']}\n" \
                           f"Total Inodes: {self.disk_metadata['inode_block_count'] * 4}\n" \
                           f"Free Inode Partitions: {self.disk_metadata['free_inode_partitions']}\n" \
                           f"Free Data Blocks: {self.disk_metadata['free_data_blocks']}"

    def _fetch_block_data_from_db(self):
        block_data = get_block_data_from_db(self.block_number)
        if block_data:
            self.status = "used"
        return block_data or self._generate_default_content()

    def _generate_default_content(self):
        if self.block_type == "boot":
            return "Bootloader and Initialization Code"
        elif self.block_type == "super":
            return "0xAA55"  # Standard Superblock Signature (can be adjusted)
        elif self.block_type == "inode":
            return "Inode Block"
        else:
            return ""

    def _populate_inodes(self):
        num_inodes_per_block = 1024 // 256  # Number of inodes per block
        inode_ids = range(self.start_inode_id, self.start_inode_id + num_inodes_per_block)
        inode_data_map = get_inode_data_from_db_batch(inode_ids)
        for inode_number in inode_ids:
            inode = Inode(inode_number)
            inode.populate_from_db(inode_data_map.get(inode_number, {}))
            self.inodes.append(inode)

    def to_dict(self):
        return {
            "block_number": self.block_number,
            "block_type": self.block_type,
            "content": self.content,
            "status": self.status,
            "inodes": [inode.to_dict() for inode in self.inodes] if self.block_type == "inode" else [],
        }

class HardDisk:
    def __init__(self, size_mb):
        if size_mb <= 0:
            raise ValueError("Disk size must be greater than 0.")
        self.size_kb = size_mb * 1024
        self.block_size = 1  # 1 KB block size
        self.num_blocks = self.size_kb // self.block_size
        self.inode_block_count = 5  # Number of inode blocks
        self.data_block_count = self.num_blocks - (2 + self.inode_block_count)  # Remaining data blocks
        self.blocks = []

        # Calculate the total number of inodes (based on 256 bytes per inode and 1 KB blocks)
        self.inodes_per_block = 1024 // 256
        self.total_inodes = self.inodes_per_block * self.inode_block_count
        self.start_inode_id = 0

        # Initialize free inodes and free data blocks arrays
        self.free_inodes = list(range(10))  # Inodes 0 to 9
        self.free_data_blocks = list(range(7, 17))  # Data blocks 7 to 16

        # Disk metadata
        self.disk_metadata = {
            "num_blocks": self.num_blocks,
            "block_size": self.block_size,
            "inode_block_count": self.inode_block_count,
            "data_block_count": self.data_block_count,
            "free_inode_partitions": self.free_inodes,
            "free_data_blocks": self.free_data_blocks
        }

        self._initialize_blocks()

    def _initialize_blocks(self):
        # Boot Block
        self.blocks.append(DiskBlock(0, "boot", "Bootloader and Initialization Code"))

        # Super Block with metadata (includes free inode and data block arrays)
        self.blocks.append(DiskBlock(1, "super", disk_metadata=self.disk_metadata))

        # Inode Blocks (Partitions)
        for i in range(self.inode_block_count):
            self.blocks.append(DiskBlock(2 + i, "inode", start_inode_id=self.start_inode_id))
            self.start_inode_id += (1024 // 256)

        # Data Blocks (Starting from block number 7)
        for i in range(self.data_block_count):
            self.blocks.append(DiskBlock(2 + self.inode_block_count + i, "data"))

    def allocate_inode(self):
        if not self.free_inodes:
            return None  # No free inodes available
        return self.free_inodes.pop(0)  # Allocate the first free inode ID

    def allocate_data_block(self):
        if not self.free_data_blocks:
            return None  # No free data blocks available
        return self.free_data_blocks.pop(0)  # Allocate the first free data block

    def deallocate_inode(self, inode_id):
        if inode_id not in self.free_inodes:  # Avoid duplicate entries
            self.free_inodes.append(inode_id)

    def deallocate_data_block(self, block_number):
        if block_number not in self.free_data_blocks:  # Avoid duplicate entries
            self.free_data_blocks.append(block_number)

    def get_disk_structure(self):
        return {
            "num_blocks": self.num_blocks,
            "block_size": self.block_size,
            "inode_block_count": self.inode_block_count,
            "data_block_count": self.data_block_count,
            "blocks": [block.to_dict() for block in self.blocks],
        }

@app5_blueprint.route("/test-db-connection", methods=["GET"])
def test_db_connection():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()
        cursor.close()
        connection.close()
        return f"Successfully connected to the database: {db_name[0]}"
    except mysql.connector.Error as e:
        app.logger.error(f"Database connection failed: {e}")
        return f"Error: {e}"

@app5_blueprint.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            # Get the disk size and generate the HardDisk object
            size_mb = int(request.form["size_mb"])
            hd = HardDisk(size_mb)
            disk_structure = hd.get_disk_structure()

            # Fetch directory structure from the database
            directory_structure = get_directory_structure()

            return render_template("visualize_disk.html", 
                                   disk_structure=disk_structure, 
                                   directory_structure=directory_structure)
        except ValueError as e:
            app.logger.error(f"Invalid disk size: {e}")
            return render_template("page5.html", error_message="Invalid disk size. Please enter a valid size.")
        except Exception as e:
            app.logger.error(f"Error: {e}")
            return render_template("page5.html", error_message=str(e))
    return render_template("page5.html", error_message=None)



# Global list to track created files
created_files = []


def insert_file_data(cursor, filename):
    try:
        # Find the first empty inode in sequence
        cursor.execute("""
            SELECT inode_id FROM inode
            WHERE filename IS NULL
            ORDER BY inode_id ASC
            LIMIT 1
        """)
        inode_result = cursor.fetchone()
        new_inode_id = inode_result[0] if inode_result else None

        # If no empty inode exists, assign the next available inode ID
        if not new_inode_id:
            cursor.execute("SELECT MAX(inode_id) FROM inode")
            max_inode = cursor.fetchone()
            new_inode_id = (max_inode[0] if max_inode[0] is not None else 0) + 1

        # Insert inode data
        cursor.execute("""
            INSERT INTO inode (inode_id, filename, file_type, size, permissions, owner, `group`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (new_inode_id, filename, 'regular', 1024, '644', 1000, 1000))

        # Find the first empty block in sequence
        cursor.execute("""
            SELECT block_number FROM file_data_blocks
            WHERE block_data IS NULL
            ORDER BY block_number ASC
            LIMIT 1
        """)
        block_result = cursor.fetchone()
        first_empty_block = block_result[0] if block_result else None

        # If no empty block exists, assign the next available block
        if not first_empty_block:
            cursor.execute("SELECT MAX(block_number) FROM file_data_blocks")
            max_block = cursor.fetchone()
            first_empty_block = (max_block[0] if max_block[0] is not None else 0) + 1

        # Insert file data into file_data_blocks
        cursor.execute("""
            INSERT INTO file_data_blocks (inode_id, block_number, block_data)
            VALUES (%s, %s, %s)
        """, (new_inode_id, first_empty_block, None))

        # Insert directory entry
        cursor.execute("""
            INSERT INTO file_directory (parent_directory, inode_id, name)
            VALUES (%s, %s, %s)
        """, (1, new_inode_id, filename))

        return new_inode_id, first_empty_block
    except Exception as e:
        print(f"Error inserting file data: {str(e)}")
        raise e


# API to handle file creation ('touch' command)
# Global flag to track if a file has been created
global file_created 
file_created= False

@app5_blueprint.route('/touch_file', methods=['POST'])
def touch_file():
    global file_created
    filename = request.json.get('filename')

    if filename:
        if file_created:
            return jsonify({"error": "You can create only one file."}), 403  # Return an error if a file already exists
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert file data and get inode ID and block number
            new_inode_id, first_empty_block = insert_file_data(cursor, filename)
            get_block_data_from_db(first_empty_block)
            conn.commit()  # Commit changes
            conn.close()

            created_files.append(filename)
            file_created = True  # Set the flag to True after the first file is created
            
            return jsonify({
                "message": f"File {filename} created successfully.",
                "filename": filename,
                "inode_id": new_inode_id,
                "block_number": first_empty_block
            }), 200
            
        except Exception as e:
            return jsonify({"error": f"Error: {str(e)}"}), 500

    return jsonify({"error": "Invalid input."}), 400

def cleanup_created_files():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for filename in created_files:
            # Fetch the inode_id of the file
            cursor.execute("SELECT inode_id FROM inode WHERE filename = %s", (filename,))
            inode_id = cursor.fetchone()

            if inode_id:
                inode_id = inode_id[0]

                # Delete corresponding records from file_data_blocks table
                cursor.execute("DELETE FROM file_data_blocks WHERE inode_id = %s", (inode_id,))

                # Delete corresponding records from file_directory table
                cursor.execute("DELETE FROM file_directory WHERE inode_id = %s", (inode_id,))

                # Delete the inode record
                cursor.execute("DELETE FROM inode WHERE inode_id = %s", (inode_id,))

        conn.commit()  # Commit all deletions
        cursor.close()
        conn.close()

        # Clear the global created_files list
        created_files.clear()
        print("All files created during the program execution have been deleted.")

    except Exception as e:
        print(f"Error during cleanup: {str(e)}")


# Register the cleanup function to run on program termination
atexit.register(cleanup_created_files)


# API to append to a file
@app5_blueprint.route('/append_file', methods=['POST'])
def append_file():
    filename = request.json.get('filename')
    content = request.json.get('content')

    if filename and content:
        if filename not in created_files:
            return jsonify({"error": f"Cannot append. The file '{filename}' was not created by you."}), 403
        
        try:
            if filename not in created_files:
                return jsonify({"error": f"File '{filename}' was not created during the current session.Updatation is restricted."}), 403

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT inode_id FROM inode WHERE filename = %s", (filename,))
            result = cursor.fetchone()

            if result:
                inode_id = result[0]
                cursor.execute("SELECT block_data FROM file_data_blocks WHERE inode_id = %s", (inode_id,))
                block_data = cursor.fetchone()

                existing_content = block_data[0] if block_data and block_data[0] else ""
                updated_content = existing_content + content + "\n"

                cursor.execute("""
                    UPDATE file_data_blocks
                    SET block_data = %s
                    WHERE inode_id = %s
                """, (updated_content, inode_id))

                conn.commit()
                conn.close()

                return jsonify({"message": f"Content appended to {filename}."}), 200
            else:
                return jsonify({"error": f"File {filename} does not exist."}), 404

        except Exception as e:
            return jsonify({"error": f"Error: {str(e)}"}), 500

    return jsonify({"error": "Invalid input."}), 400


@app5_blueprint.route('/rm_file', methods=['POST'])
def rm_file():
    global file_created  # Declare the global variable

    filename = request.json.get('filename')

    try:
        if filename not in created_files:
            return jsonify({"error": f"File '{filename}' was not created during the current session. Deletion is restricted."}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the file or directory exists in the inode table
        cursor.execute("SELECT inode_id FROM inode WHERE filename = %s", (filename,))
        result = cursor.fetchone()

        if result:
            inode_id = result[0]

            # Check if the file is a directory and has children
            cursor.execute("SELECT COUNT(*) FROM file_directory WHERE parent_directory = %s", (inode_id,))
            child_count = cursor.fetchone()[0]

            if child_count > 0:
                return jsonify({"error": f"Directory '{filename}' is not empty. Please remove its contents first."}), 403

            # Delete file data from file_data_blocks table
            cursor.execute("DELETE FROM file_data_blocks WHERE inode_id = %s", (inode_id,))

            # Delete the file or directory record from file_directory table
            cursor.execute("DELETE FROM file_directory WHERE inode_id = %s", (inode_id,))

            # Delete the inode record
            cursor.execute("DELETE FROM inode WHERE inode_id = %s", (inode_id,))
            conn.commit()

            cursor.close()
            conn.close()

            # Remove the filename from the global created_files list
            if filename in created_files:
                created_files.remove(filename)

            # Set file_created flag to False after deletion
            file_created = False  # Ensure the flag is set to False here

            return jsonify({"message": f"File or directory '{filename}' deleted successfully."}), 200

        else:
            return jsonify({"error": "File or directory not found."}), 404

    except Exception as e:
        print(f"Error while deleting file or directory: {str(e)}")
        return jsonify({"error": f"Error: {str(e)}"}), 500

  # API to read a file
@app5_blueprint.route('/read_file', methods=['POST'])
def read_file():
    filename = request.json.get('filename')

    if filename:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Retrieve the inode_id for the given filename
            cursor.execute("SELECT inode_id FROM inode WHERE filename = %s", (filename,))
            result = cursor.fetchone()

            if result:
                inode_id = result[0]

                # Check if the parent inode of the file is 1
                cursor.execute("SELECT parent_directory FROM file_directory WHERE inode_id = %s", (inode_id,))
                parent_inode = cursor.fetchone()

                if parent_inode and parent_inode[0] == 1:  # Ensure the parent inode is 1
                    # Retrieve the content of the file
                    cursor.execute("SELECT block_data FROM file_data_blocks WHERE inode_id = %s", (inode_id,))
                    block_data = cursor.fetchone()

                    if block_data:
                        return jsonify({"content": block_data[0]}), 200
                    else:
                        return jsonify({"error": "No content found for this file."}), 404
                else:
                    return jsonify({"error": f"File '{filename}' not present in current path"}), 403
            else:
                return jsonify({"error": f"File '{filename}' does not exist."}), 404

        except Exception as e:
            return jsonify({"error": f"Error: {str(e)}"}), 500

        finally:
            conn.close()

    return jsonify({"error": "Invalid input."}), 400

@app5_blueprint.route('/get_hard_disk', methods=['GET'])
def get_hard_disk():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all the blocks from the file_data_blocks table
        cursor.execute("SELECT block_number, inode_id, block_data FROM file_data_blocks")
        blocks = cursor.fetchall()

        block_list = [{"block_number": block[0], "inode_id": block[1], "block_data": block[2]} for block in blocks]

        conn.close()

        return jsonify({"blocks": block_list}), 200

    except Exception as e:
        return jsonify({"error": f"Error fetching hard disk: {str(e)}"}), 500

app.register_blueprint(app5_blueprint, url_prefix='/app5')


if __name__ == "__main__":
    app.run(debug=True, port=5015)
