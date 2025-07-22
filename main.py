from flask import Flask, render_template, redirect, url_for  # Import redirect here as well # type: ignore
from Floder1.app1 import app1_blueprint
from Floder2.app2 import app2_blueprint
from Floder3.app3 import app3_blueprint
from Floder4.app4 import app4_blueprint
from Floder5.app5 import app5_blueprint

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(app1_blueprint, url_prefix='/app1')
app.register_blueprint(app2_blueprint, url_prefix='/app2')
app.register_blueprint(app3_blueprint, url_prefix='/app3')
app.register_blueprint(app4_blueprint, url_prefix='/app4')
app.register_blueprint(app5_blueprint, url_prefix='/app5')


@app.route('/')
def home():
    return redirect(url_for('app1.index'))  # Redirect to the first GUI page

if __name__ == '__main__':
    app.run(debug=True,port="5002")
