from flask import Flask, jsonify, send_file, send_from_directory
import os
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Use absolute path to ensure files are found regardless of where the script is run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dictionary to map junction IDs to their names
JUNCTIONS = {
    1: "Big Ben", 
    2: "Gariahat",
    3: "Jadavpur",
    4: "Times Square",
    5: "Rasbehari",
    6: "Garia",
    7: "Tollygunge",
    8: "Chingrihata",
    9: "Saltlake"
}

@app.route('/api/junctions')
def get_junctions():
    """Return the list of all available junctions."""
    locations = [{"id": k, "name": v} for k, v in JUNCTIONS.items()]
    return jsonify(locations)

@app.route('/api/data/<int:timeframe>')
def get_data(timeframe):
    """
    Read the corresponding output_{timeframe}.csv and return congestion stats.
    The current application assumes files are placed under directories named '0' or '5'.
    """
    try:
        # Construct the path to the CSV file
        csv_path = os.path.join(BASE_DIR, str(timeframe), f"output_{timeframe}.csv")
        data = pd.read_csv(csv_path, header=None)
        
        # Structure the response
        stats = {}
        # Iterate over the valid junction IDs
        for i in range(1, 10):
            val = float(data.iloc[i-1][1])
            stats[str(i)] = {
                "duration_mins": val,
                "progress_percent": min(100, int(val * 20)) # Cap at 100%
            }
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route('/api/image/<int:timeframe>/<int:junction_id>')
def serve_image(timeframe, junction_id):
    """Serve the image for a specific junction and timeframe."""
    try:
        image_path = os.path.join(BASE_DIR, str(timeframe), f"{junction_id}.jpg")
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == '__main__':
    # Run the server on localhost port 5001
    app.run(host='127.0.0.1', port=5001, debug=True)
