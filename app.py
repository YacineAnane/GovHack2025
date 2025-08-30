from flask import Flask, render_template, jsonify
import requests
import json

from permits_plots import plot_permits_choropleth



app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/testing")
def testing():
    # Call your plotting function
    fig = plot_permits_choropleth("All")

    # Convert to HTML (includes JS for interactivity)
    fig_html = fig.to_html(full_html=False)

    return render_template("testing.html", plot=fig_html)


@app.route("/api/public_transport")
def get_transport_data():
    with open("static/public_transport_stops.geojson") as f:
        data = json.load(f)
    return jsonify(data)
    # url = "https://opendata.transport.vic.gov.au/dataset/6d36dfd9-8693-4552-8a03-05eb29a391fd/resource/afa7b823-0c8b-47a1-bc40-ada565f684c7/download/public_transport_stops.geojson"
    # resp = requests.get(url)
    # print(resp)

    


@app.route("/housing-stress")
def housing_stress():
    return render_template("housing-stress.html")



if __name__ == "__main__":
    app.run(debug=True)
