from flask import Flask

def create_app():
    app = Flask(__name__)
    #app.configure[""]

    from .routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    return app