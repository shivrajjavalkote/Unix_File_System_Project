from flask import Blueprint, render_template, redirect  # Import redirect

app1_blueprint = Blueprint('app1', __name__, template_folder='templates', static_folder='static')

@app1_blueprint.route('/')
def index():
    return render_template('index.html')  # First GUI page

@app1_blueprint.route('/navigate_to_page2')
def navigate_to_page2():
    return redirect('/app2/page2')  # Navigate to the second page
