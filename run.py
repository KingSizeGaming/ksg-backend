# run.py
from dotenv import load_dotenv

load_dotenv()

from app import (
    create_app,
)  # Make sure this is the correct import path for your factory function

app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
